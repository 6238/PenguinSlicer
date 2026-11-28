"""The shared set of plates for the two placement checks (contracts/plate-configuration.md,
"Shared plates for the placement checks"): the slice service's placement check gives every
plate's expected answer, and the set is exactly what scripts/make_placement_parts.py writes.

Each plate goes through the slice service's front door, as any plate does: its parts are
uploaded with POST /parts and the plate is submitted with POST /slices, whose answer is
compared with the plate's `expected`; an instance with a `rotation` is placed by the code's
own placement of a rotation. One thing is turned on the way in: until every setting under
Orca's own name is built (item 6 of README-details.md's phase 2), the plate's
`enable_support` is given as the `supports` override the code as built reads.
"""
import hashlib
import json
import math
import re
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from helpers import CONTRACTS, Parts, submit, upload
from make_placement_parts import POSTS, make_plates, write_post
from penguin_slice import plate, service
from penguin_slice.errors import error_report
from penguin_slice.jobs import JobPool
from penguin_slice.mesh import orientation_footprints, read_binary_stl
from penguin_slice.web import create_app, slice_worker

PLACEMENT = CONTRACTS / "examples" / "placement"
PARTS = CONTRACTS / "examples" / "parts"
PLATE_CONFIGURATION_DOC = (CONTRACTS / "plate-configuration.md").read_text()

# The plates the contract's table asks for, with the answer of each.
EXPECTED = {
    "margin-pass.json": {"accepted": True},
    "margin-fail.json": {"code": "slice.placement_off_plate", "instance": "Bracket #1"},
    "height-pass.json": {"accepted": True},
    "height-fail.json": {"code": "slice.placement_too_tall", "instance": "Post-341 #1"},
    "height-laid-down-pass.json": {"accepted": True},
    "spacing-pass.json": {"accepted": True},
    "spacing-fail.json": {"code": "slice.placement_too_close", "instance": "Bracket #1",
                          "other_instance": "Bracket #2"},
    "spacing-supports-pass.json": {"accepted": True},
    "spacing-supports-fail.json": {"code": "slice.placement_too_close", "instance": "Bracket #1",
                                   "other_instance": "Bracket #2"},
    "angle-pass.json": {"accepted": True},
    "angle-fail.json": {"code": "slice.placement_too_close", "instance": "Bracket #1",
                        "other_instance": "Bracket #2"},
    "rotation-pass.json": {"accepted": True},
    "rotation-fail.json": {"code": "slice.placement_too_close", "instance": "Bracket #1",
                           "other_instance": "Spacer #1"},
}
PLATES = sorted(EXPECTED)

# What each plate tries: the distance that decides it and the rule's figure, in mm.
FIGURES = {"margin": plate.MARGIN_MM, "spacing": plate.SPACING_MM, "spacing-supports": plate.SPACING_SUPPORTS_MM,
           "angle": plate.SPACING_MM, "rotation": plate.SPACING_MM}
PRINTABLE = {"min": (0.0, 0.0), "max": (340.0, 320.0), "height": 340.0}     # the default set's H2S


def load(name):
    return json.loads((PLACEMENT / name).read_text())


def file_of_hash():
    return {hashlib.sha256(path.read_bytes()).hexdigest(): path for path in PARTS.glob("*.stl")}


def contract_fields(heading):
    """The field names of the first table under `heading` in the plate configuration contract."""
    text = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^#)", PLATE_CONFIGURATION_DOC, re.M | re.S).group(1)
    return [m.group(1) for m in re.finditer(r"^\| `([a-z0-9_]+)` \|", text, re.M)]


def quaternion_matrix(rotation):
    """The contract's matrix of a `rotation` [w, x, y, z], divided by its length first."""
    length = math.sqrt(sum(v * v for v in rotation))
    w, x, y, z = (v / length for v in rotation)
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)))


def quaternion_product(a, b):
    """The quaternion of the turn b followed by the turn a (its matrix is M(a) M(b))."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw]


def with_overrides_as_built(plate_configuration):
    """The plate with `enable_support` as the `supports` override the code as built reads
    (see the module's text); every other field as the plate has it."""
    configuration = json.loads(json.dumps(plate_configuration))
    overrides = configuration.pop("overrides", {})
    if "enable_support" in overrides:
        configuration["overrides"] = {"supports": "on" if overrides["enable_support"] == "1" else "off"}
    return configuration


def front_door(directory):
    """A slice service's HTTP interface with every part of contracts/examples/parts/ uploaded
    through it under USER_KEY, its slice jobs held (never run)."""
    pool = JobPool(slice_worker, executor=type("Held", (), {"submit": lambda self, *a: None})(),
                   error_report=error_report)
    client = create_app(Path(directory) / "work", pool, start_sweeper=False).test_client()
    for path in PARTS.glob("*.stl"):
        assert upload(client, path.read_bytes()).status_code == 201, path.name
    return client


def answer(plate_configuration, directory):
    """The answer of POST /slices to the plate, in the form of a plate's `expected`."""
    reply = submit(front_door(directory), with_overrides_as_built(plate_configuration))
    if reply.status_code == 202:
        return {"accepted": True}
    report = reply.get_json()
    return {"code": report["code"], **{k: report["where"][k] for k in ("instance", "other_instance")
                                        if k in report["where"]}}


def placed(plate_configuration, directory):
    """The plate's instances' hulls on the plate, from the footprints the code makes for each
    (service's own steps 4 and 5 up to the placement rules, which this measures)."""
    parts = Parts(directory)
    for path in PARTS.glob("*.stl"):
        parts.add(path.read_bytes())
    instances = [service._normalised(i) for i in plate_configuration["instances"]]
    entries = {ref: service._checked_part(ref, part, parts.find()(part["sha256"], part["units"]),
                                          service.largest_plate())
               for ref, part in plate_configuration["parts"].items()}
    service._place_rotations(instances, entries)
    return [plate.instance_hull(i, entries[i["ref"]].footprints[plate.turn_of(i)]) for i in instances]


class TestTheSet:
    def test_the_set_holds_exactly_the_plates_of_the_contract(self):
        assert sorted(p.name for p in PLACEMENT.iterdir()) == PLATES

    def test_the_set_is_what_the_script_writes(self):
        written = make_plates()
        assert sorted(written) == PLATES
        for name, text in written.items():
            assert (PLACEMENT / name).read_text() == text, name

    @pytest.mark.parametrize("name", PLATES)
    def test_each_plate_expects_what_the_contract_asks(self, name):
        assert load(name)["expected"] == EXPECTED[name]

    @pytest.mark.parametrize("name", PLATES)
    def test_each_plate_has_the_contracts_form(self, name):
        data = load(name)
        assert list(data) == ["description", "plate_configuration", "expected"]
        assert isinstance(data["description"], str) and data["description"]
        configuration = data["plate_configuration"]
        assert set(configuration) <= set(contract_fields("### Fields in phase 2"))
        assert {"plate_id", "submission_id", "parts", "instances"} <= set(configuration)
        assert not {"printer", "filament", "process"} & set(configuration)        # the default set
        assert set(configuration["overrides"]) == {"enable_support"}
        for value in (configuration["plate_id"], configuration["submission_id"]):
            assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)
        files = file_of_hash()
        for part in configuration["parts"].values():
            assert list(part) == contract_fields("### A part in phase 2")
            assert part["units"] == "mm" and part["sha256"] in files
        for part in configuration["parts"].values():
            assert isinstance(part["name"], str) and part["name"]
        for instance in configuration["instances"]:
            assert set(instance) <= set(contract_fields("### An instance in phase 2"))
            assert {"ref", "angle", "x", "y"} <= set(instance)
            assert instance["ref"] in configuration["parts"]
            assert ("orientation" in instance) != ("rotation" in instance)
            if "rotation" in instance:
                rotation = instance["rotation"]
                assert isinstance(rotation, list) and len(rotation) == 4
                assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rotation)
                assert abs(math.hypot(*rotation) - 1) <= 1e-6
            else:
                assert instance["orientation"] in {"+z", "-z", "+x", "-x", "+y", "-y"}
            assert type(instance["angle"]) is int and 0 <= instance["angle"] <= 359
            for key in ("x", "y"):
                assert isinstance(instance[key], (int, float)) and not isinstance(instance[key], bool)
                assert math.isfinite(instance[key])

    def test_every_plate_has_its_own_ids(self):
        ids = [load(name)["plate_configuration"][k] for name in PLATES for k in ("plate_id", "submission_id")]
        assert len(set(ids)) == len(ids)


class TestThePosts:
    @pytest.mark.parametrize("name,height", sorted(POSTS.items()))
    def test_each_post_is_what_the_script_writes(self, tmp_path, name, height):
        written = tmp_path / name
        assert write_post(written, height) == 12
        assert (PARTS / name).read_bytes() == written.read_bytes()

    @pytest.mark.parametrize("name,height", sorted(POSTS.items()))
    def test_each_post_is_a_closed_box_of_its_size(self, name, height):
        mesh = read_binary_stl((PARTS / name).read_bytes(), name)
        assert mesh.triangles == 12 and mesh.health["watertight"]
        footprint = orientation_footprints(mesh)["+z"]
        assert footprint["height"] == height
        xs, ys = zip(*footprint["hull"])
        assert (max(xs) - min(xs), max(ys) - min(ys)) == (10.0, 10.0)


class TestThePlacementCheck:
    @pytest.mark.parametrize("name", PLATES)
    def test_each_plate_gets_its_expected_answer(self, tmp_path, name):
        data = load(name)
        assert answer(data["plate_configuration"], tmp_path) == data["expected"]

    @pytest.mark.parametrize("name", [n for n in PLATES if not n.startswith("height")])
    def test_each_plate_is_a_hundredth_from_its_figure(self, tmp_path, name):
        """The distance that decides the plate, measured from the placed footprints, is the
        rule's figure plus 0.01 mm on a passing plate and less 0.01 mm on a failing one."""
        hulls = placed(load(name)["plate_configuration"], tmp_path)
        rule = name.rsplit("-", 1)[0]
        if rule == "margin":
            (hull,) = hulls
            measured = min(min(p[0] - PRINTABLE["min"][0], PRINTABLE["max"][0] - p[0],
                               p[1] - PRINTABLE["min"][1], PRINTABLE["max"][1] - p[1]) for p in hull)
        else:
            first, second = hulls
            measured = Polygon(first).distance(Polygon(second))
        step = 0.01 if name.endswith("-pass.json") else -0.01
        # The footprints keep their points to 0.001 mm (mesh._footprint), so a measure
        # from them is within about 0.0007 mm of the exact distance the script set.
        assert measured == pytest.approx(FIGURES[rule] + step, abs=1e-3)

    def test_the_tall_post_fails_standing_and_passes_laid_down(self):
        standing = load("height-fail.json")["plate_configuration"]
        laid = load("height-laid-down-pass.json")["plate_configuration"]
        assert standing["parts"] == laid["parts"]
        assert [i["orientation"] for i in standing["instances"]] == ["+z"]
        assert [i["orientation"] for i in laid["instances"]] != ["+z"]

    def test_the_codes_matrix_of_a_rotation_is_the_contracts(self):
        for verdict in ("pass", "fail"):
            for instance in load(f"rotation-{verdict}.json")["plate_configuration"]["instances"]:
                if "rotation" in instance:
                    for got, expected in zip(plate.quaternion_matrix(instance["rotation"]),
                                             quaternion_matrix(instance["rotation"])):
                        assert list(got) == pytest.approx(list(expected), abs=1e-12)

    def test_the_rotation_plates_turn_with_an_angle_after_the_rotation(self):
        """The rotation plates try an angle applied after a rotation (Rz(angle) M)."""
        for verdict in ("pass", "fail"):
            (laid,) = [i for i in load(f"rotation-{verdict}.json")["plate_configuration"]["instances"]
                       if "rotation" in i]
            assert laid["angle"] != 0

    @pytest.mark.parametrize("wrong", ["inverse", "angle-first"])
    def test_the_rotation_plates_tell_the_contracts_turn_from_a_wrong_one(self, tmp_path, wrong):
        """A check that turns by the inverse of the rotation (the transposed matrix, or the
        quaternion's sign the wrong way round), or that turns by the angle before the rotation
        (M Rz(angle)), gets a different answer on at least one rotation plate."""
        answers = []
        for verdict in ("pass", "fail"):
            data = load(f"rotation-{verdict}.json")
            configuration = json.loads(json.dumps(data["plate_configuration"]))
            for instance in configuration["instances"]:
                if "rotation" in instance:
                    w, x, y, z = instance["rotation"]
                    if wrong == "inverse":
                        instance["rotation"] = [w, -x, -y, -z]
                    else:
                        half = math.radians(instance.pop("angle")) / 2
                        instance["rotation"] = quaternion_product([w, x, y, z],
                                                                  [math.cos(half), 0.0, 0.0, math.sin(half)])
                        instance["angle"] = 0
            answers.append(answer(configuration, tmp_path) == data["expected"])
        assert not all(answers)

    def test_the_pairs_differ_only_in_the_figure(self):
        """Each failing plate is its passing plate with one instance moved, and the supports
        plates differ from the plain ones only in enable_support and the distance."""
        for rule in ("margin", "spacing", "spacing-supports", "angle", "rotation", "height"):
            passing = load(f"{rule}-pass.json")["plate_configuration"]
            failing = load(f"{rule}-fail.json")["plate_configuration"]
            for key in ("overrides",):
                assert passing[key] == failing[key], rule
            if rule != "height":
                assert passing["parts"] == failing["parts"], rule
                assert [{k: v for k, v in i.items() if k not in ("x", "y")} for i in passing["instances"]] == \
                    [{k: v for k, v in i.items() if k not in ("x", "y")} for i in failing["instances"]], rule
        assert load("spacing-supports-pass.json")["plate_configuration"]["overrides"] == {"enable_support": "1"}
        assert load("spacing-pass.json")["plate_configuration"]["overrides"] == {"enable_support": "0"}
