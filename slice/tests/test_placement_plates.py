"""The shared set of plates for the two placement checks (contracts/plate-configuration.md,
"Shared plates for the placement checks"): the slice service's placement check gives every
plate's expected answer, and the set is exactly what scripts/make_placement_parts.py writes.

Until the phase 2 plate configuration is built (items 1 to 4 of README-details.md, "Phase 2:
one machine"), each plate is turned into the plate configuration as built here: a part named
by hash becomes the file of that hash in contracts/examples/parts/, `enable_support` becomes
the `supports` override, and an instance with a `rotation` becomes an instance standing `+z`
of a copy of its part turned by that rotation's matrix, which places it exactly as the
contract's one transform does.
"""
import hashlib
import json
import math
import re
import struct
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from helpers import CONTRACTS, mesh_stl
from make_placement_parts import POSTS, make_plates, write_post
from penguin_slice import plate
from penguin_slice.errors import error_report
from penguin_slice.mesh import orientation_footprints, read_binary_stl
from penguin_slice.service import read_plate_configuration

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


def turned_stl(path, rotation):
    """The part's STL with every vertex turned by the rotation's matrix (`v' = M v`)."""
    data = path.read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    m = quaternion_matrix(rotation)
    vertices = []
    for i in range(count):
        corners = struct.unpack("<12fH", data[84 + 50 * i: 134 + 50 * i])[3:12]
        for k in range(3):
            v = corners[3 * k: 3 * k + 3]
            vertices.append([sum(m[r][c] * v[c] for c in range(3)) for r in range(3)])
    return mesh_stl(vertices, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(count)])


def as_built(plate_configuration, directory):
    """The plate configuration in the form the code as built reads (see the module's text)."""
    files = file_of_hash()
    parts = {key: {"name": part["name"], "stl": str(files[part["sha256"]])}
             for key, part in plate_configuration["parts"].items()}
    instances = []
    for i, instance in enumerate(plate_configuration["instances"]):
        instance = dict(instance)
        if "rotation" in instance:
            key = f"{instance['ref']}-turned-{i}"
            source = plate_configuration["parts"][instance["ref"]]
            turned = directory / f"{key}.stl"
            turned.write_bytes(turned_stl(files[source["sha256"]], instance.pop("rotation")))
            parts[key] = {"name": source["name"], "stl": str(turned)}
            instance.update(ref=key, orientation="+z")
        instances.append(instance)
    overrides = plate_configuration.get("overrides", {})
    built = {"parts": parts, "instances": instances}
    if "enable_support" in overrides:
        built["overrides"] = {"supports": "on" if overrides["enable_support"] == "1" else "off"}
    return built


def answer(plate_configuration, directory):
    """The answer of the slice service's checks, in the form of a plate's `expected`."""
    try:
        read_plate_configuration(as_built(plate_configuration, directory), directory)
    except Exception as exc:  # noqa: BLE001 -- every refusal becomes its error report
        report = error_report(exc)
        return {"code": report["code"], **{k: report["where"][k] for k in ("instance", "other_instance")
                                            if k in report["where"]}}
    return {"accepted": True}


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
        for instance in configuration["instances"]:
            assert set(instance) <= set(contract_fields("### An instance in phase 2"))
            assert ("orientation" in instance) != ("rotation" in instance)
            if "rotation" in instance:
                assert abs(math.hypot(*instance["rotation"]) - 1) <= 1e-6

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
        configuration = as_built(load(name)["plate_configuration"], tmp_path)
        footprints = {key: orientation_footprints(read_binary_stl(Path(part["stl"]).read_bytes(), key))
                      for key, part in configuration["parts"].items()}
        hulls = [plate.instance_hull(i, footprints[i["ref"]][i["orientation"]]) for i in configuration["instances"]]
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
