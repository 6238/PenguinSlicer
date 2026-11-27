#!/usr/bin/env python3
"""Write the shared set of plates for the two placement checks, and its two posts.

contracts/plate-configuration.md, "Shared plates for the placement checks", fixes the set:
one JSON file for each plate in contracts/examples/placement/, over the parts of
contracts/examples/parts/, two of which this script writes: post-340.stl and post-341.stl,
boxes of 10 by 10 by 340 mm and 10 by 10 by 341 mm (12 triangles each).

For each rule one plate just passes and one just fails, 0.01 mm from the rule's figure. The
distances are computed here with geometry of this script's own, from the contract's
Coordinates and its rotation's matrix, never with the slice service's code, so that the
slice service's tests (tests/test_placement_plates.py) check its placement check against an
independent computation, and the wizard's tests check the wizard's against the same plates.

Deterministic: the checked-in files must equal the output byte for byte. Run it after a
change to a rule or a figure, and change both components' tests in the same commit.
"""
import hashlib
import json
import math
import struct
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PARTS = REPO / "contracts" / "examples" / "parts"
PLACEMENT = REPO / "contracts" / "examples" / "placement"

POSTS = {"post-340.stl": 340.0, "post-341.stl": 341.0}
POST_SIDE_MM = 10.0

# The default set of profiles' plate (a Bambu Lab H2S) and the placement rules' figures.
PLATE_MIN, PLATE_MAX, PLATE_HEIGHT = (0.0, 0.0), (340.0, 320.0), 340.0
MARGIN_MM, SPACING_MM, SPACING_SUPPORTS_MM = 3.0, 5.0, 12.0
STEP_MM = 0.01          # each plate's distance from its rule's figure
PLACES = 6              # decimals of a computed position: within 1e-6 mm of the distance asked

ORIENTATION_MATRICES = {
    '+z': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    '+x': ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
}

# The bracket laid on the face of its convex hull across the L's open corner, the face
# through the edge (40, 10)-(10, 30): its outward normal n = (2, 3, 0) / sqrt(13) turned onto
# (0, 0, -1), a quarter turn about n x (0, 0, -1). The same rotation as the contract's
# example, to 9 decimals.
_HALF = math.sqrt(0.5)
LAID_BRACKET = [round(_HALF, 9), round(-_HALF * 3 / math.sqrt(13), 9), round(_HALF * 2 / math.sqrt(13), 9), 0.0]


def quaternion_product(a, b):
    """The quaternion of the turn b followed by the turn a (its matrix is M(a) M(b))."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw]


# The rotation plates' turn: LAID_BRACKET followed by 30 degrees about the vertical, so the same
# hull face lies on the plate. LAID_BRACKET alone is a quarter turn about a horizontal axis,
# and on the bracket (z only 0 and 12) it and its inverse give the same
# footprint; this one does not (50.59 x 15.19 mm against 41.48 x 33.20 mm), so a check that
# turns by the transposed matrix gets another answer. The plates also turn it by
# ROTATION_ANGLE after the rotation, so a check that applies the angle first does too.
LAID_BRACKET_TURNED = [round(v, 9) for v in quaternion_product(
    [math.cos(math.radians(15)), 0.0, 0.0, math.sin(math.radians(15))], LAID_BRACKET)]
ROTATION_ANGLE = 15


# ---- the posts -----------------------------------------------------------------------

def _normal(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(x * x for x in n))
    return tuple(x / length for x in n)


def post_triangles(height):
    """A closed box POST_SIDE_MM by POST_SIDE_MM by `height` on the origin, wound outwards."""
    s = POST_SIDE_MM
    corner = [(x, y, z) for z in (0.0, height) for y in (0.0, s) for x in (0.0, s)]
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return [tuple(corner[i] for i in face) for face in faces]


def post_bytes(height):
    tris = post_triangles(height)
    header = f"PenguinSlicer placement post {POST_SIDE_MM:g}x{POST_SIDE_MM:g}x{height:g} mm".encode()
    body = [header.ljust(80, b"\0"), struct.pack("<I", len(tris))]
    for a, b, c in tris:
        body.append(struct.pack("<12fH", *_normal(a, b, c), *a, *b, *c, 0))
    return b"".join(body)


def write_post(path, height):
    """Write one post's binary STL; returns its triangles."""
    Path(path).write_bytes(post_bytes(height))
    return len(post_triangles(height))


# ---- geometry, from the contract's Coordinates ---------------------------------------

def rotation_matrix(rotation):
    """The contract's matrix of a unit quaternion [w, x, y, z], divided by its length."""
    length = math.sqrt(sum(v * v for v in rotation))
    w, x, y, z = (v / length for v in rotation)
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)))


def stl_vertices(data):
    count = struct.unpack("<I", data[80:84])[0]
    vertices = []
    for i in range(count):
        corners = struct.unpack("<12fH", data[84 + 50 * i: 134 + 50 * i])[3:12]
        vertices.extend(corners[k: k + 3] for k in (0, 3, 6))
    return vertices


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    """Counterclockwise, by the monotone chain."""
    points = sorted(set(points))
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def footprint(data, instance):
    """(hull about the footprint's centre, height): the part turned by its orientation or
    rotation, its hull seen from above, centred on the turned bounding box's centre in x, y."""
    m = rotation_matrix(instance["rotation"]) if "rotation" in instance else \
        ORIENTATION_MATRICES[instance["orientation"]]
    turned = [tuple(sum(m[r][c] * v[c] for c in range(3)) for r in range(3)) for v in stl_vertices(data)]
    cx = (min(v[0] for v in turned) + max(v[0] for v in turned)) / 2
    cy = (min(v[1] for v in turned) + max(v[1] for v in turned)) / 2
    height = max(v[2] for v in turned) - min(v[2] for v in turned)
    return [(x - cx, y - cy) for x, y in convex_hull([(v[0], v[1]) for v in turned])], height


def placed(hull, angle, x, y):
    """The hull turned `angle` degrees counterclockwise about its centre and moved to (x, y)."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(c * px - s * py + x, s * px + c * py + y) for px, py in hull]


def _point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _inside(p, hull):
    return all(_cross(hull[i], hull[(i + 1) % len(hull)], p) >= 0 for i in range(len(hull)))


def _edges(hull):
    return [(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull))]


def _crosses(a, b, c, d):
    return _cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0


def distance(first, second):
    """The least distance between two convex polygons, 0 when they meet."""
    if any(_inside(p, second) for p in first) or any(_inside(p, first) for p in second) or \
            any(_crosses(a, b, c, d) for a, b in _edges(first) for c, d in _edges(second)):
        return 0.0
    return min(min(_point_segment(p, a, b) for p in first for a, b in _edges(second)),
               min(_point_segment(p, a, b) for p in second for a, b in _edges(first)))


def edge_distance(hull):
    """How far the hull stays inside the printable area: its least distance to an edge."""
    return min(min(x - PLATE_MIN[0], PLATE_MAX[0] - x, y - PLATE_MIN[1], PLATE_MAX[1] - y) for x, y in hull)


def solve_x(fixed, moving, angle, y, target):
    """The x at which `moving` (a hull about its centre, at `angle`, at height `y`) lies
    `target` mm from `fixed`, to the right of it. The distance of two convex shapes, one
    moved along a line, is a convex function of the move, so it rises from where they meet."""
    lo = min(p[0] for p in fixed)
    hi = lo + 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if distance(fixed, placed(moving, angle, mid, y)) < target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, PLACES)


# ---- the plates ----------------------------------------------------------------------

def _parts_bytes():
    parts = {name: (PARTS / name).read_bytes() for name in ("bracket.stl", "spacer.stl")}
    parts.update({name: post_bytes(height) for name, height in POSTS.items()})
    return parts


def _ids(name):
    def make(kind):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/6238/PenguinSlicer/contracts/examples/"
                                                  f"placement/{name}#{kind}"))
    return {"plate_id": make("plate"), "submission_id": make("submission")}


def _plate(name, description, parts, instances, supports, expected):
    configuration = {**_ids(name), "parts": parts, "instances": instances,
                     "overrides": {"enable_support": "1" if supports else "0"}}
    return name, {"description": description, "plate_configuration": configuration, "expected": expected}


def _check(data, configuration, rule_ok):
    """Every plate lies inside the plate and its instances apart, by more than STEP_MM,
    except for the one distance the plate tries (`rule_ok` says which are left out)."""
    hulls, heights = [], []
    for instance in configuration["instances"]:
        part = configuration["parts"][instance["ref"]]
        hull, height = footprint(data[part["sha256"]], instance)
        hulls.append(placed(hull, instance["angle"], instance["x"], instance["y"]))
        heights.append(height)
    for hull, height in zip(hulls, heights):
        assert rule_ok == "margin" or edge_distance(hull) > MARGIN_MM + 1.0, configuration
        assert rule_ok == "height" or height < PLATE_HEIGHT - 1.0, configuration
    if len(hulls) == 2:
        assert rule_ok == "spacing" or distance(*hulls) > SPACING_SUPPORTS_MM + 1.0, configuration
    return hulls


def make_plates():
    """{file name: text} of every plate of the set."""
    files = _parts_bytes()
    sha = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    data = {sha[name]: files[name] for name in files}

    def part(key_name, file):
        return {"name": key_name, "sha256": sha[file], "units": "mm"}

    bracket = {"bracket": part("Bracket", "bracket.stl")}
    plates = []

    # The 3 mm margin: the bracket's footprint 3.01 and 2.99 mm inside the left edge.
    hull, _ = footprint(files["bracket.stl"], {"orientation": "+z"})
    for verdict, gap in (("pass", MARGIN_MM + STEP_MM), ("fail", MARGIN_MM - STEP_MM)):
        x = round(PLATE_MIN[0] + gap - min(p[0] for p in hull), PLACES)
        plates.append(_plate(
            f"margin-{verdict}.json",
            f"A bracket whose footprint is {gap:.2f} mm inside the printable area's edge, supports off",
            bracket, [{"ref": "bracket", "orientation": "+z", "angle": 0, "x": x, "y": 160.0}], False,
            {"accepted": True} if verdict == "pass" else
            {"code": "slice.placement_off_plate", "instance": "Bracket #1"}))

    # The printable height: the posts standing up, and the taller one laid down.
    for file, verdict in (("post-340.stl", "pass"), ("post-341.stl", "fail")):
        height = POSTS[file]
        name = file[:-len(".stl")].capitalize()
        description = (f"A {POST_SIDE_MM:g} by {POST_SIDE_MM:g} by {height:g} mm post standing up, "
                       + ("exactly the printable height" if verdict == "pass" else
                          f"{height - PLATE_HEIGHT:g} mm taller than the printable height") + ", supports off")
        plates.append(_plate(
            f"height-{verdict}.json", description, {"post": part(name, file)},
            [{"ref": "post", "orientation": "+z", "angle": 0, "x": 170.0, "y": 160.0}], False,
            {"accepted": True} if verdict == "pass" else
            {"code": "slice.placement_too_tall", "instance": "Post-341 #1"}))
    plates.append(_plate(
        "height-laid-down-pass.json",
        "The 341 mm post laid on its side and turned 30 degrees, so that it fits inside the margin, supports off",
        {"post": part("Post-341", "post-341.stl")},
        [{"ref": "post", "orientation": "+x", "angle": 30, "x": 170.0, "y": 160.0}], False, {"accepted": True}))

    # The spacings: a second instance moved along x until the gap is the figure +- 0.01 mm.
    pairs = (
        ("spacing", SPACING_MM, False, {"orientation": "+z"}, 0, "bracket", 0,
         "Two brackets {gap:.2f} mm apart with supports off"),
        ("spacing-supports", SPACING_SUPPORTS_MM, True, {"orientation": "+z"}, 0, "bracket", 0,
         "Two brackets {gap:.2f} mm apart with supports on"),
        ("angle", SPACING_MM, False, {"orientation": "+z"}, 37, "bracket", 0,
         "A bracket turned 37 degrees, {gap:.2f} mm from an unturned bracket at the closest point of their "
         "outlines, supports off"),
        ("rotation", SPACING_MM, False, {"rotation": LAID_BRACKET_TURNED}, ROTATION_ANGLE, "spacer", 0,
         "A bracket laid by a rotation on the face of its convex hull across the L's open corner and turned "
         f"{ROTATION_ANGLE} degrees, {{gap:.2f}} mm from a spacer, supports off"),
    )
    for rule, figure, supports, turn, angle, other, other_angle, description in pairs:
        parts = dict(bracket)
        if other == "spacer":
            parts["spacer"] = part("Spacer", "spacer.stl")
        fixed_hull, _ = footprint(files["bracket.stl"], turn)
        fixed = placed(fixed_hull, angle, 100.0, 160.0)
        moving, _ = footprint(files[f"{other}.stl"], {"orientation": "+z"})
        for verdict, gap in (("pass", figure + STEP_MM), ("fail", figure - STEP_MM)):
            x = solve_x(fixed, moving, other_angle, 160.0, gap)
            second = "Spacer #1" if other == "spacer" else "Bracket #2"
            plates.append(_plate(
                f"{rule}-{verdict}.json", description.format(gap=gap), parts,
                [{"ref": "bracket", **turn, "angle": angle, "x": 100.0, "y": 160.0},
                 {"ref": other, "orientation": "+z", "angle": other_angle, "x": x, "y": 160.0}], supports,
                {"accepted": True} if verdict == "pass" else
                {"code": "slice.placement_too_close", "instance": "Bracket #1", "other_instance": second}))

    texts = {}
    for name, plate in plates:
        rule = name.rsplit("-", 1)[0]
        _check(data, plate["plate_configuration"],
               "margin" if rule == "margin" else "height" if rule.startswith("height") else "spacing")
        texts[name] = json.dumps(plate, indent=2) + "\n"
    return texts


def main():
    for name, height in POSTS.items():
        write_post(PARTS / name, height)
        print(f"wrote {PARTS / name}")
    PLACEMENT.mkdir(exist_ok=True)
    for name, text in make_plates().items():
        (PLACEMENT / name).write_text(text)
        print(f"wrote {PLACEMENT / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
