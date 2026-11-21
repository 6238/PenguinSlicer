"""The plate: orientations, instance placement and the rules a placement must pass.

Each orientation is named by the part axis that ends up pointing up. The matrices are
row-major rotations applied to the part's vertices (v' = M v).

This is the authority on placement: the slice service checks every plate configuration here before
slicing. A user interface that checks placement while the student drags keeps its own
twin of this geometry and tests it against tests/fixtures/plate_cases.json, the same
cases tests/test_plate.py reads.
"""
import math
import re

from shapely.geometry import Polygon

# The least distance between two footprints, with supports off and on (slice/README.md,
# "Spacing"): measured with the pinned Orca on pairs of the team's real parts, every pair
# tried sliced 1 mm apart with supports off, and with supports on Orca refused pairs up to
# 8 mm apart (their supports' paths meet, return code -101) and sliced every pair at 8.5 mm.
SPACING_MM = 5.0
SPACING_SUPPORTS_MM = 12.0      # 8.5 mm measured, with 3.5 mm to spare
MARGIN_MM = 3.0         # every footprint stays this far inside the printable area
EPS_MM = 1e-6

ORIENTATIONS = ('+z', '-z', '+x', '-x', '+y', '-y')

ORIENTATION_MATRICES = {
    '+z': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    '-z': ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
    '+x': ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
    '-x': ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    '+y': ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    '-y': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
}

PART_NAME_MAX_CHARS = 40
_NOT_NAME_CHAR = re.compile(r'[^A-Za-z0-9_-]')

OFF_PLATE_MESSAGE = "{label} is not fully on the plate."
TOO_TALL_MESSAGE = "{label} is taller than the printer can print ({height:g} mm)."
TOO_CLOSE_MESSAGE = "{label} and {label2} are closer than {spacing:g} mm."
TOO_CLOSE_SUPPORTS_MESSAGE = ("{label} and {label2} are closer than {spacing:g} mm, the room supports need between "
                              "instances.")
# The remedies for two instances too close together, whether the placement check or Orca
# found them (errors.CODES, slicer.orca_failure).
TOO_CLOSE_REMEDY = ("Spread the instances out (or press Arrange), or move some instances to a second plate, "
                    "and slice again.")
TOO_CLOSE_SUPPORTS_REMEDY = ("Spread the instances out (or press Arrange), turn supports off, or move some instances "
                             "to a second plate, and slice again.")


def _cos_sin(angle):
    """cos and sin of `angle` degrees, exact on multiples of 90."""
    if angle % 90 == 0:
        return {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}[int(angle // 90) % 4]
    radians = math.radians(angle)
    return math.cos(radians), math.sin(radians)


def instance_matrix(orientation, angle, offset, x, y):
    """The instance's 3x4 [M | t]: M = Rz(angle) R_o, t = (x, y, 0) - Rz(angle) offset, so that
    p_plate = M p_part + t puts the footprint's centre at (x, y) and its lowest point at z 0."""
    c, s = _cos_sin(angle)
    rz = ((c, -s, 0), (s, c, 0), (0, 0, 1))
    r_o = ORIENTATION_MATRICES[orientation]
    m = [[sum(rz[i][k] * r_o[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    moved = [sum(rz[i][k] * offset[k] for k in range(3)) for i in range(3)]
    t = (x - moved[0], y - moved[1], -moved[2])
    return [m[i] + [t[i]] for i in range(3)]


def plate_from_printer(printer, supports=False):
    """The plate the checks use, from an Orca printer profile; its spacing is
    SPACING_SUPPORTS_MM when the plate is sliced with supports, else SPACING_MM."""
    corners = [tuple(float(v) for v in corner.lower().split('x')) for corner in printer['printable_area']]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return {'min': [min(xs), min(ys)], 'max': [max(xs), max(ys)],
            'height': float(printer['printable_height']), 'margin': MARGIN_MM,
            'spacing': SPACING_SUPPORTS_MM if supports else SPACING_MM, 'supports': bool(supports),
            'printer': printer.get('name')}


def instance_hull(instance, footprint):
    """The footprint's hull turned by the instance's angle and moved to its (x, y)."""
    c, s = _cos_sin(instance['angle'])
    return [[c * px - s * py + instance['x'], s * px + c * py + instance['y']] for px, py in footprint['hull']]


def sanitize_part_name(name):
    """The part name in the file-name character set: letters, digits, - and _; every other
    character becomes _, at most 40 characters, `part` when nothing is left."""
    return _NOT_NAME_CHAR.sub('_', name)[:PART_NAME_MAX_CHARS] or 'part'


def instance_labels(names):
    """`<sanitized name> #<n>` per instance, n counting each sanitized name in list order."""
    counts, labels = {}, []
    for name in names:
        clean = sanitize_part_name(name)
        counts[clean] = counts.get(clean, 0) + 1
        labels.append(f'{clean} #{counts[clean]}')
    return labels


def check_placement(instances, parts, plate):
    """The placement's problems: every off_plate, then every too_tall, then every too_close
    pair (i, j), i < j. Each is {'rule', 'instances', 'message'}; an empty list passes."""
    labels = instance_labels([parts[instance['ref']]['name'] for instance in instances])
    footprints = [parts[instance['ref']]['footprints'][instance['orientation']] for instance in instances]
    hulls = [instance_hull(instance, footprint) for instance, footprint in zip(instances, footprints)]
    lo = [plate['min'][i] + plate['margin'] - EPS_MM for i in (0, 1)]
    hi = [plate['max'][i] - plate['margin'] + EPS_MM for i in (0, 1)]
    problems = []
    for i, hull in enumerate(hulls):
        if any(not lo[k] <= point[k] <= hi[k] for point in hull for k in (0, 1)):
            problems.append({'rule': 'off_plate', 'instances': [i],
                             'message': OFF_PLATE_MESSAGE.format(label=labels[i])})
    for i, footprint in enumerate(footprints):
        if footprint['height'] > plate['height'] + EPS_MM:
            problems.append({'rule': 'too_tall', 'instances': [i],
                             'message': TOO_TALL_MESSAGE.format(label=labels[i], height=plate['height'])})
    polygons = [Polygon(hull) for hull in hulls]
    too_close = TOO_CLOSE_SUPPORTS_MESSAGE if plate.get('supports') else TOO_CLOSE_MESSAGE
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            if polygons[i].distance(polygons[j]) < plate['spacing'] - EPS_MM:
                problems.append({'rule': 'too_close', 'instances': [i, j],
                                 'message': too_close.format(label=labels[i], label2=labels[j],
                                                             spacing=plate['spacing'])})
    return problems
