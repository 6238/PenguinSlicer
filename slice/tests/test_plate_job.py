"""run_plate_job (plate_job.py) with slice_plate replaced: no Orca run."""
import json
from pathlib import Path
from unittest import mock

import pytest

from helpers import make_part, write_names_archive
from penguin_slice import plate_job
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE
from penguin_slice.plate_job import JobPart, PlateJob, run_plate_job
from penguin_slice.slicer import DEFAULT_PROFILES, SliceError, SliceResult


def job_part(directory, name, size):
    part = make_part(directory, name, size)
    return JobPart(name=part['name'], stl_path=part['stl_path'], footprints=part['footprints'], triangles=12)


@pytest.fixture
def scratch(tmp_path):
    path = tmp_path / 'scratch'
    path.mkdir()
    return path


@pytest.fixture
def job(tmp_path):
    stls = tmp_path / 'stls'
    stls.mkdir()
    parts = {'box': job_part(stls, 'Box', (20, 20, 10)), 'peg': job_part(stls, 'Peg', (8, 8, 30))}
    copies = [{'ref': 'box', 'orientation': '+z', 'angle': 0, 'x': 50.0, 'y': 50.0},
              {'ref': 'box', 'orientation': '+z', 'angle': 90, 'x': 100.0, 'y': 50.0},
              {'ref': 'peg', 'orientation': '+x', 'angle': 15, 'x': 150.0, 'y': 50.0}]
    return PlateJob(copies=copies, parts=parts, profiles=DEFAULT_PROFILES, overrides={'wall_loops': '4'},
                    filament=None, process=None, delivered_name='Box_plus1-20261009-1432.gcode.3mf')


def fake_slice_plate(names, calls):
    def fake(model_3mf, profiles, output_dir, *args, **kwargs):
        calls.append((Path(model_3mf), profiles, Path(output_dir), args, kwargs))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        archive = Path(output_dir) / 'plate.gcode.3mf'
        write_names_archive(archive, names)
        return SliceResult(output_path=archive, print_time_s=60.0, filament_m=1.0, filament_g=3.0,
                           layer_count=40, warnings=[])
    return fake


def test_job_triangles_sum_over_copies(job):
    assert job.triangles() == 36


def test_names_match_passes_with_the_jobs_own_process_file(job, scratch):
    calls = []
    with mock.patch.object(plate_job, 'slice_plate', fake_slice_plate(['Peg #1', 'Box #2', 'Box #1'], calls)):
        result = run_plate_job(job, scratch)
    assert result.layer_count == 40
    model, profiles, output_dir, args, kwargs = calls[0]
    assert model == scratch / 'plate.3mf' and model.is_file()
    assert output_dir == scratch / 'slice'
    # slice_plate's own timeout, PLATE_SLICE_TIMEOUT_S; no stop and no progress callback given
    assert (args, kwargs) == ((), {"stop": None, "on_progress": None, "memory_ceiling_mb": None})
    # The process file is the job's own, written in scratch with the overrides merged.
    assert (profiles.printer, profiles.filament) == (DEFAULT_PROFILES.printer, DEFAULT_PROFILES.filament)
    assert profiles.process == scratch / 'process.json'
    merged = json.loads(profiles.process.read_text())
    original = json.loads(DEFAULT_PROFILES.process.read_text())
    assert merged == dict(original, wall_loops='4')


@pytest.mark.parametrize('names', [['Box #1', 'Box #2'], ['Box #1', 'Box #2', ''],
                                   ['Box #1', 'Box #2', 'Peg #1', 'Peg #1']])
def test_missing_name_fails_left_off(job, scratch, names):
    with mock.patch.object(plate_job, 'slice_plate', fake_slice_plate(names, [])):
        with pytest.raises(SliceError) as caught:
            run_plate_job(job, scratch)
    assert caught.value.message == LEFT_OFF_MESSAGE


def test_slice_error_passes_through(job, scratch):
    def refuse(*args, **kwargs):
        raise SliceError("Parts are too close together; spread them out.", "exit code 155", -101)

    with mock.patch.object(plate_job, 'slice_plate', refuse), pytest.raises(SliceError) as caught:
        run_plate_job(job, scratch)
    assert caught.value.code == -101
