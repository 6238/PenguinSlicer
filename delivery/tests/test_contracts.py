"""Printer delivery against contracts/: the error report it emits has the shape of the
contract's example, and the sliced file's name and plate are the ones the sliced-file
contract promises. Printer delivery never imports another component; these files are the
only place the two meet."""
import json
import os
import re

import pytest

from penguin_delivery_daemon import printer as daemon_printer
from penguin_delivery_relay import errors
from penguin_delivery_relay import relay as relay_module

CONTRACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'contracts')


def read(name):
    with open(os.path.join(CONTRACTS, name), encoding='utf-8') as fh:
        return fh.read()


ERROR_REPORT = json.loads(read('examples/error-report.json'))
SLICED_FILE = json.loads(read('examples/sliced-file.json'))


def contract_fields():
    """The error report's fields as contracts/error-report.md lists them: name -> required."""
    fields = {}
    for match in re.finditer(r'^\| `(\w+)` \| (\w+) \| (yes|no) \|', read('error-report.md'),
                             re.MULTILINE):
        fields[match.group(1)] = match.group(3) == 'yes'
    return fields


def test_the_contract_lists_the_fields_this_test_expects():
    assert contract_fields() == {'code': True, 'message': True, 'where': False,
                                 'remedy': True, 'action': False, 'retryable': True,
                                 'detail': True}


@pytest.mark.parametrize('text', [
    'Printer offline, last seen 7 min ago',        # a refused send, with `where`
    'File not found or expired',                   # with `where` and `action`
    'Too Many Requests: 10 per 1 minute',          # with neither
    'download answered 404',                       # the fallback
])
def test_an_emitted_error_report_has_the_shape_of_the_contract_example(text):
    report = errors.error_report(text)
    fields = contract_fields()
    assert {f for f, required in fields.items() if required} <= set(report) <= set(fields)
    for field, value in report.items():
        assert type(value) is type(ERROR_REPORT[field]), field
    assert set(report.get('where', {})) <= set(ERROR_REPORT['where'])
    component, _, what = report['code'].partition('.')
    assert (component, bool(what)) == ('delivery', True)
    assert re.fullmatch(r'[a-z]+\.[a-z_]+', ERROR_REPORT['code'])
    assert re.fullmatch(r'[a-z]+\.[a-z_]+', report['code'])


def test_the_sliced_file_example_name_round_trips_through_the_job_suffix():
    name = SLICED_FILE['file']
    assert name.endswith('.gcode.3mf')
    job_id = relay_module.new_job_id()
    remote = daemon_printer.suffixed_name(name, job_id)
    assert remote == f"{name[:-len('.gcode.3mf')]}-{job_id}.gcode.3mf"
    assert daemon_printer.strip_job_suffix(remote) == name
    assert relay_module.strip_job_suffix(remote) == name
    # The contract promises the name never already looks suffixed.
    assert daemon_printer.strip_job_suffix(name) == name
    assert relay_module.strip_job_suffix(name) == name


def test_the_plate_the_daemon_starts_is_the_one_plate_of_the_sliced_file_contract():
    plates = set(re.findall(r'Metadata/plate_(\d+)\.gcode`', read('sliced-file.md')))
    assert plates == {str(daemon_printer.PLATE_NUMBER)}
    assert 'There is always exactly one plate, plate 1' in read('sliced-file.md')
