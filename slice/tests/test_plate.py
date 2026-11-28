"""Plate geometry in plate.py, checked against tests/fixtures/plate_cases.json, this file's own
cases. The wizard's twin of this geometry is held to the shared set of plates in
contracts/examples/placement/ instead (tests/test_placement_plates.py)."""
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
                      'supports': False, 'printer': 'Bambu Lab H2S 0.6 nozzle'}
    assert result == CASES['plate']


def test_with_supports_the_plate_asks_for_the_larger_spacing():
    result = plate.plate_from_printer(default_printer_profile(), supports=True)
    assert (result['spacing'], result['supports']) == (plate.SPACING_SUPPORTS_MM, True)
    assert plate.SPACING_SUPPORTS_MM > plate.SPACING_MM


@pytest.mark.parametrize('supports, gap, message', [
    (False, 4.9, 'Square #1 and Square #2 are closer than 5 mm.'),
    (False, 5.0, None),
    (True, 5.0, 'Square #1 and Square #2 are closer than {s:g} mm, the room supports need between instances.'),
    (True, 'spacing', None),
])
def test_the_spacing_depends_on_supports(supports, gap, message):
    """Two 20 mm squares side by side, `gap` mm apart: refused below the plate's spacing,
    with the sentence that says supports need the room when they are on."""
    plate_ = plate.plate_from_printer(default_printer_profile(), supports=supports)
    gap = plate.SPACING_SUPPORTS_MM if gap == 'spacing' else gap
    square = {'hull': [[-10, -10], [10, -10], [10, 10], [-10, 10]], 'height': 5, 'offset': [0, 0, 0]}
    parts = {'sq': {'name': 'Square', 'footprints': {'+z': square}}}
    instances = [{'ref': 'sq', 'orientation': '+z', 'angle': 0, 'x': 100.0, 'y': 100.0},
                 {'ref': 'sq', 'orientation': '+z', 'angle': 0, 'x': 120.0 + gap, 'y': 100.0}]
    problems = plate.check_placement(instances, parts, plate_)
    expected = [] if message is None else [{'rule': 'too_close', 'instances': [0, 1],
                                           'message': message.format(s=plate.SPACING_SUPPORTS_MM)}]
    assert problems == expected


def test_constants():
    assert (plate.SPACING_MM, plate.SPACING_SUPPORTS_MM, plate.MARGIN_MM, plate.EPS_MM) == (5.0, 12.0, 3.0, 1e-6)


def test_instance_hull_rotates_then_moves():
    footprint = {'hull': [[-2, -1], [2, -1], [2, 1], [-2, 1]], 'height': 1, 'offset': [0, 0, 0]}
    hull = plate.instance_hull({'angle': 90, 'x': 10, 'y': 20}, footprint)
    assert [[round(v, 9) + 0.0 for v in p] for p in hull] == [[11, 18], [11, 22], [9, 22], [9, 18]]


class TestRotation:
    """An instance's `rotation`, a unit quaternion [w, x, y, z] (contracts/plate-configuration.md,
    "An instance in phase 2"): its matrix, and the one transform for both forms of a turn."""

    def test_the_identity_and_a_quarter_turn_about_z(self):
        assert plate.quaternion_matrix((1, 0, 0, 0)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        half = 0.5 ** 0.5
        m = plate.quaternion_matrix((half, 0, 0, half))
        assert [list(row) for row in m] == [pytest.approx(r, abs=1e-12) for r in ([0, -1, 0], [1, 0, 0], [0, 0, 1])]

    def test_each_orientation_has_a_rotation_with_its_matrix(self):
        half = 0.5 ** 0.5
        quaternions = {'+z': (1, 0, 0, 0), '-z': (0, 1, 0, 0), '+x': (half, 0, -half, 0), '-x': (half, 0, half, 0),
                       '+y': (half, half, 0, 0), '-y': (half, -half, 0, 0)}
        for name, q in quaternions.items():
            m = plate.quaternion_matrix(q)
            for row, expected in zip(m, plate.ORIENTATION_MATRICES[name]):
                assert list(row) == pytest.approx(list(expected), abs=1e-12), name

    def test_q_and_minus_q_are_one_turn(self):
        q = (0.707106781, -0.588348405, 0.39223227, 0.0)
        for row, minus in zip(plate.quaternion_matrix(q), plate.quaternion_matrix(tuple(-v for v in q))):
            assert list(row) == pytest.approx(list(minus), abs=1e-15)

    def test_a_rotation_is_divided_by_its_length(self):
        assert plate.quaternion_matrix((2, 0, 0, 0)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def test_the_turn_of_an_instance(self):
        assert plate.turn_of({'orientation': '-x'}) == '-x'
        assert plate.turn_of({'rotation': [1.0, 0.0, 0.0, 0.0]}) == (1.0, 0.0, 0.0, 0.0)
        assert plate.turn_matrix('-x') == plate.ORIENTATION_MATRICES['-x']
        assert plate.turn_matrix((1.0, 0.0, 0.0, 0.0)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def test_the_transform_of_a_rotation_is_rz_angle_after_m(self):
        half = 0.5 ** 0.5
        offset = [1.0, 2.0, 3.0]
        by_rotation = plate.instance_matrix((half, 0, -half, 0), 30, offset, 100.0, 50.0)
        by_orientation = plate.instance_matrix('+x', 30, offset, 100.0, 50.0)
        for row, expected in zip(by_rotation, by_orientation):
            assert row == pytest.approx(expected, abs=1e-12)


def test_sanitize_edge_cases():
    assert plate.sanitize_part_name('') == 'part'
    assert plate.sanitize_part_name('x' * 41) == 'x' * 40
    assert plate.sanitize_part_name('Bracket v2.1') == 'Bracket_v2_1'
