"""Plate geometry in plate.py, checked against tests/fixtures/plate_cases.json, the cases a
user interface's twin of this geometry is also tested against."""
import json

import pytest

from helpers import FIXTURES
from penguin_slice import plate
from penguin_slice.slicer import default_printer_profile

CASES = json.loads((FIXTURES / 'plate_cases.json').read_text())


def test_shared_cases_cover_every_rule():
    names = [case['name'] for case in CASES['cases']]
    for required in ('all_clear', 'off_plate_left', 'off_plate_after_45_rotation', 'exactly_on_margin',
                     'too_tall', 'overlap', 'four_mm_apart', 'exactly_spacing_apart',
                     'rotated_near_miss', 'same_name_two_parts', 'wedge_turned_30_fits',
                     'wedge_turned_330_off_plate'):
        assert required in names


@pytest.mark.parametrize('case', CASES['cases'], ids=[case['name'] for case in CASES['cases']])
def test_shared_case(case):
    assert case['instances'], 'make_rotated_cases.py has filled the case'
    assert plate.check_placement(case['instances'], CASES['parts'], CASES['plate']) == case['problems']


@pytest.mark.parametrize('entry', CASES['matrices'], ids=lambda e: f"{e['orientation']}@{e['angle']}")
def test_shared_matrix(entry):
    matrix = plate.instance_matrix(entry['orientation'], entry['angle'], entry['offset'], entry['x'], entry['y'])
    assert len(matrix) == 3
    for row, expected in zip(matrix, entry['matrix']):
        assert row == pytest.approx(expected, abs=1e-9)


def test_shared_labels_and_sanitize():
    for entry in CASES['labels']:
        assert plate.instance_labels(entry['names']) == entry['labels']
    for entry in CASES['sanitize']:
        assert plate.sanitize_part_name(entry['in']) == entry['out']


@pytest.mark.parametrize('name', plate.ORIENTATIONS)
@pytest.mark.parametrize('angle', (0, 37.5, 90))
def test_matrices_put_named_axis_up(name, angle):
    axis = [0, 0, 0]
    axis['xyz'.index(name[1])] = 1 if name[0] == '+' else -1
    matrix = plate.instance_matrix(name, angle, [0, 0, 0], 0, 0)
    up = [sum(matrix[r][c] * axis[c] for c in range(3)) for r in range(3)]
    assert up == pytest.approx([0, 0, 1], abs=1e-12)


def test_matrix_places_the_footprint_centre_at_x_y():
    # The offset (footprint centre, lowest z) lands on (x, y, 0), whatever the angle.
    offset = [7.0, -3.0, -11.0]
    matrix = plate.instance_matrix('+z', 33, offset, 120, 80)
    moved = [sum(matrix[r][c] * offset[c] for c in range(3)) + matrix[r][3] for r in range(3)]
    assert moved == pytest.approx([120, 80, 0], abs=1e-9)


@pytest.mark.parametrize('angle, expected', [(0, (1, 0)), (90, (0, 1)), (180, (-1, 0)), (270, (0, -1)),
                                             (450, (0, 1)), (-90, (0, -1))])
def test_quarter_turns_are_exact(angle, expected):
    assert plate._cos_sin(angle) == expected


def test_plate_from_default_printer():
    result = plate.plate_from_printer(default_printer_profile())
    assert result == {'min': [0, 0], 'max': [340, 320], 'height': 340, 'margin': 3.0, 'spacing': 5.0,
                      'printer': 'Bambu Lab H2S 0.6 nozzle'}
    assert result == CASES['plate']


def test_constants():
    assert (plate.SPACING_MM, plate.MARGIN_MM, plate.EPS_MM) == (5.0, 3.0, 1e-6)


def test_instance_hull_rotates_then_moves():
    footprint = {'hull': [[-2, -1], [2, -1], [2, 1], [-2, 1]], 'height': 1, 'offset': [0, 0, 0]}
    hull = plate.instance_hull({'angle': 90, 'x': 10, 'y': 20}, footprint)
    assert [[round(v, 9) + 0.0 for v in p] for p in hull] == [[11, 18], [11, 22], [9, 22], [9, 18]]


def test_sanitize_edge_cases():
    assert plate.sanitize_part_name('') == 'part'
    assert plate.sanitize_part_name('x' * 41) == 'x' * 40
    assert plate.sanitize_part_name('Bracket v2.1') == 'Bracket_v2_1'
