"""run_plate_configuration (plate_configuration.py) with slice_plate replaced: no Orca run."""
import json
from pathlib import Path
from unittest import mock

import pytest

from helpers import make_part, write_names_archive
from penguin_slice import plate_configuration
from penguin_slice.errors import error_report
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE
from penguin_slice.plate_configuration import (ONE_INSTANCE_MEMORY_REMEDY, ONE_INSTANCE_TIMEOUT_REMEDY, CheckedPart,
                                               PlateConfiguration, run_plate_configuration)
from penguin_slice.slicer import DEFAULT_PROFILES, SliceError, SliceResult


def checked_part(directory, name, size):
    part = make_part(directory, name, size)
    return CheckedPart(name=part['name'], stl_path=part['stl_path'], footprints=part['footprints'], triangles=12)


@pytest.fixture
def scratch(tmp_path):
    path = tmp_path / 'scratch'
    path.mkdir()
    return path


@pytest.fixture
def configuration(tmp_path):
    stls = tmp_path / 'stls'
    stls.mkdir()
    parts = {'box': checked_part(stls, 'Box', (20, 20, 10)), 'peg': checked_part(stls, 'Peg', (8, 8, 30))}
    instances = [{'ref': 'box', 'orientation': '+z', 'angle': 0, 'x': 50.0, 'y': 50.0},
                 {'ref': 'box', 'orientation': '+z', 'angle': 90, 'x': 100.0, 'y': 50.0},
                 {'ref': 'peg', 'orientation': '+x', 'angle': 15, 'x': 150.0, 'y': 50.0}]
    return PlateConfiguration(instances=instances, parts=parts, profiles=DEFAULT_PROFILES,
                              overrides={'wall_loops': '4'}, filament=None, process=None,
                              delivered_name='Box_plus1-20261009-1432.gcode.3mf')


def fake_slice_plate(names, calls):
    def fake(model_3mf, profiles, output_dir, *args, **kwargs):
        calls.append((Path(model_3mf), profiles, Path(output_dir), args, kwargs))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        archive = Path(output_dir) / 'plate.gcode.3mf'
        write_names_archive(archive, names)
        return SliceResult(output_path=archive, print_time_s=60.0, filament_m=1.0, filament_g=3.0,
                           layer_count=40, warnings=[])
    return fake


def test_triangles_sum_over_instances(configuration):
    assert configuration.triangles() == 36


def test_names_match_passes_with_the_slice_jobs_own_process_file(configuration, scratch):
    calls = []
    with mock.patch.object(plate_configuration, 'slice_plate',
                           fake_slice_plate(['Peg #1', 'Box #2', 'Box #1'], calls)):
        result = run_plate_configuration(configuration, scratch)
    assert result.layer_count == 40
    model, profiles, output_dir, args, kwargs = calls[0]
    assert model == scratch / 'plate.3mf' and model.is_file()
    assert output_dir == scratch / 'slice'
    # slice_plate's own timeout, PLATE_SLICE_TIMEOUT_S; no stop and no progress callback given
    assert (args, kwargs) == ((), {"stop": None, "on_progress": None, "memory_ceiling_mb": None})
    # The process file is the slice job's own, written in scratch with the overrides merged.
    assert (profiles.printer, profiles.filament) == (DEFAULT_PROFILES.printer, DEFAULT_PROFILES.filament)
    assert profiles.process == scratch / 'process.json'
    merged = json.loads(profiles.process.read_text())
    original = json.loads(DEFAULT_PROFILES.process.read_text())
    assert merged == dict(original, wall_loops='4')


def test_a_setting_of_each_kind_and_form_reaches_the_process_file(configuration, scratch):
    """Checked by the table (settings_table.validate_overrides), each value reaches the process
    file Orca is given exactly as it was sent."""
    from penguin_slice.settings_table import validate_overrides
    one_of_each = {'wall_loops': '5', 'layer_height': '0.28', 'sparse_infill_density': '35%',
                   'initial_layer_line_width': '120%', 'outer_wall_line_width': '0.65',
                   'sparse_infill_pattern': 'gyroid', 'enable_support': '1', 'extra_solid_infills': '7'}
    configuration.overrides = validate_overrides(one_of_each)
    calls = []
    with mock.patch.object(plate_configuration, 'slice_plate',
                           fake_slice_plate(['Peg #1', 'Box #2', 'Box #1'], calls)):
        run_plate_configuration(configuration, scratch)
    written = json.loads(calls[0][1].process.read_text())
    assert {name: written[name] for name in one_of_each} == one_of_each
    original = json.loads(DEFAULT_PROFILES.process.read_text())
    assert {k: v for k, v in written.items() if k not in one_of_each} == \
        {k: v for k, v in original.items() if k not in one_of_each}       # only those replaced


@pytest.mark.parametrize('names', [['Box #1', 'Box #2'], ['Box #1', 'Box #2', ''],
                                   ['Box #1', 'Box #2', 'Peg #1', 'Peg #1']])
def test_missing_name_fails_left_off(configuration, scratch, names):
    with mock.patch.object(plate_configuration, 'slice_plate', fake_slice_plate(names, [])):
        with pytest.raises(SliceError) as caught:
            run_plate_configuration(configuration, scratch)
    assert caught.value.message == LEFT_OFF_MESSAGE


def test_slice_error_passes_through(configuration, scratch):
    def refuse(*args, **kwargs):
        raise SliceError("Two instances are too close together.", "exit code 155", -101)

    with mock.patch.object(plate_configuration, 'slice_plate', refuse), pytest.raises(SliceError) as caught:
        run_plate_configuration(configuration, scratch)
    assert caught.value.code == -101


@pytest.mark.parametrize('code, remedy', [('slice.timeout', ONE_INSTANCE_TIMEOUT_REMEDY),
                                          ('slice.out_of_memory', ONE_INSTANCE_MEMORY_REMEDY)])
@pytest.mark.parametrize('count', [1, 2])
def test_a_plate_of_one_instance_is_never_told_to_slice_fewer(configuration, scratch, code, remedy, count):
    """With one instance there is none to remove: the remedy is the part's, with no action."""
    configuration.instances = configuration.instances[:count]

    def stop(*args, **kwargs):
        raise SliceError("The slicer took too long on this plate.", "stopped", error_code=code)

    with mock.patch.object(plate_configuration, 'slice_plate', stop), pytest.raises(SliceError) as caught:
        run_plate_configuration(configuration, scratch)
    report = error_report(caught.value)
    if count == 1:
        assert report['remedy'] == remedy and 'action' not in report
    else:
        assert 'instances' in report['remedy'] and report['action'] == 'lower_quantities'
