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


SLICED_FILE = json.loads(read('examples/sliced-file.json'))

# The contract's type words, as Python types. A report is JSON, so `number` is int or float.
_TYPES = {'string': (str,), 'object': (dict,), 'boolean': (bool,), 'number': (int, float),
          'integer': (int,)}


def contract_fields(name='error-report.md'):
    """The fields as the contract's table lists them: name -> (type word, required).

    Read from the contract itself, never from its example: another component may replace
    the example with any other valid report at any time."""
    fields = {}
    for match in re.finditer(r'^\| `(\w+)` \| (\w+) \| ([^|]+?) \|', read(name),
                             re.MULTILINE):
        fields[match.group(1)] = (match.group(2), match.group(3).strip())
    return fields


def where_keys():
    """The keys the contract allows inside `where`, from its own sentence."""
    row = re.search(r'^\| `where` \|.*$', read('error-report.md'), re.MULTILINE).group(0)
    return set(re.findall(r'`(\w+)`', row.split('Any of', 1)[1]))


def assert_is_an_error_report(report):
    fields = contract_fields()
    required = {f for f, (_t, req) in fields.items() if req == 'yes'}
    assert required <= set(report) <= set(fields), sorted(report)
    for field, value in report.items():
        type_word = fields[field][0]
        assert isinstance(value, _TYPES[type_word]), field
        if type_word == 'number':
            assert not isinstance(value, bool), field
    assert set(report.get('where', {})) <= where_keys()
    assert re.fullmatch(r'delivery\.[a-z_]+', report['code'])
    assert report['message'].endswith('.') and report['remedy'].endswith('.')


def test_the_contract_lists_the_fields_this_test_expects():
    fields = contract_fields()
    assert {f: req for f, (_t, req) in fields.items()} == {
        'code': 'yes', 'message': 'yes', 'where': 'no', 'remedy': 'yes', 'action': 'no',
        'retryable': 'yes', 'detail': 'yes'}
    assert where_keys() == {'part', 'instance', 'other_instance', 'height_mm', 'stage'}


def test_the_example_is_itself_a_valid_report_whatever_its_values():
    """Only the fields: the values belong to whichever component wrote the example."""
    example = json.loads(read('examples/error-report.json'))
    required = {f for f, (_t, req) in contract_fields().items() if req == 'yes'}
    assert required <= set(example)


@pytest.mark.parametrize('text', [
    'Printer offline, last seen 7 min ago',        # a refused send, with `where`
    'File not found or expired',                   # with `where` and `action`
    'Too Many Requests: 10 per 1 minute',          # with neither
    'download answered 404',                       # the fallback
])
def test_an_emitted_error_report_has_the_contract_shape(text):
    assert_is_an_error_report(errors.error_report(text))


def test_every_code_printer_delivery_knows_builds_a_contract_report():
    for code in errors.CODES:
        assert_is_an_error_report(errors.report_for_code(code, detail='evidence'))


def progress_states():
    row = re.search(r'^\| `state` \|.*$', read('progress-report.md'), re.MULTILINE).group(0)
    return set(re.findall(r'`(\w+)`', row.split('One of', 1)[1].split('.', 1)[0]))


def test_every_delivery_progress_report_has_the_contract_shape(tmp_path):
    """A whole delivery job and a failed one, through the relay: every report has the
    required fields of contracts/progress-report.md with their types, a contract state,
    `error` exactly when failed (itself an error report), and a sequence that rises."""
    from link_faults import Shop
    fields = contract_fields('progress-report.md')
    assert progress_states() == {'queued', 'running', 'done', 'failed', 'cancelled'}
    required = {f for f, (_t, req) in fields.items() if req == 'yes'}
    for fail in (False, True):
        folder = tmp_path / ('failed' if fail else 'done')
        folder.mkdir()
        shop = Shop(folder)
        shop.online()
        if fail:
            shop.link.inject('download', *['wrong_content'] * 3)
        job_id = shop.send()
        assert shop.drive(900, lambda: shop.final(job_id))
        reports = [r for r in shop.reports if r['job'] == job_id]
        sequences = [r['sequence'] for r in reports]
        assert sequences == sorted(sequences)
        for report in reports:
            assert required <= set(report), sorted(report)
            for field, (type_word, _req) in fields.items():
                if field in report and type_word in _TYPES:
                    assert isinstance(report[field], _TYPES[type_word]), field
            assert report['state'] in progress_states()
            assert ('error' in report) == (report['state'] == 'failed')
            if 'error' in report:
                assert_is_an_error_report(report['error'])
            if 'fraction' in report:
                assert 0 <= report['fraction'] <= 1
        assert reports[-1]['state'] == ('failed' if fail else 'done')


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
