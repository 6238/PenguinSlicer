"""The contract documents and their examples against the code, so neither can drift.

contracts/plate-configuration.md and contracts/sliced-file.md are read as Markdown: the
first column of each field table must list exactly the fields the code reads or writes, the
limits table must give the code's values, and the examples must go through the code.
"""
import ast
import json
import re
import zipfile

import pytest

from helpers import CONTRACTS, PLATE_ID, SLICE_ROOT, SUBMISSION_ID, Parts, install_fake_orca, sha256
from penguin_slice import limits, plate, service
from penguin_slice.errors import CODES
from penguin_slice.service import slice_plate_configuration
from penguin_slice.slicer import GCODE_ENTRY, PLATE_JSON_ENTRY, SLICE_INFO_ENTRY

PLATE_CONFIGURATION_DOC = (CONTRACTS / "plate-configuration.md").read_text()
SLICED_FILE_DOC = (CONTRACTS / "sliced-file.md").read_text()
PLATE_CONFIGURATION_EXAMPLE = CONTRACTS / "examples" / "plate-configuration.json"
EXAMPLE_PARTS = CONTRACTS / "examples" / "parts"          # the files the example's `stl` names are sent from
SLICED_FILE_EXAMPLE = CONTRACTS / "examples" / "sliced-file.json"


def section(doc, heading):
    """The text under `heading` (a whole heading line) up to the next heading of any level."""
    match = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^#)", doc + "\n#", re.M | re.S)
    assert match, f"no section {heading!r}"
    return match.group(1)


def table(doc, heading):
    """The rows of the first table in a section, as lists of cells, without header and rule."""
    rows = [line.strip() for line in section(doc, heading).splitlines() if line.strip().startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def names(doc, heading):
    return [re.fullmatch(r"`([^`]+)`", row[0]).group(1) for row in table(doc, heading)]


# The four overrides of the form before phase 2 (the contract's "Overrides"), under Orca's names.
OLD_OVERRIDES = {"infill": lambda v: ("sparse_infill_density", f"{v}%"), "walls": lambda v: ("wall_loops", str(v)),
                 "supports": lambda v: ("enable_support", "1" if v == "on" else "0"),
                 "brim": lambda v: ("brim_type", {"auto": "auto_brim", "off": "no_brim", "outer": "outer_only"}[v])}


def phase_2_of_the_example():
    """examples/plate-configuration.json, the plate of the contract's Example, in its phase 2
    form: each part named by the hash of its file and "mm", with a plate id and a submission,
    and its overrides under Orca's own names."""
    data = json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text())
    for part in data["parts"].values():
        part.update(sha256=sha256((EXAMPLE_PARTS / part.pop("stl")).read_bytes()), units="mm")
    data["overrides"] = dict(OLD_OVERRIDES[key](value) for key, value in data["overrides"].items())
    return {"plate_id": PLATE_ID, "submission_id": SUBMISSION_ID, **data}


def example_parts(tmp_path):
    parts = Parts(tmp_path)
    for path in EXAMPLE_PARTS.glob("*.stl"):
        parts.add(path.read_bytes())
    return parts


class TestPlateConfigurationDocument:
    def test_fields(self):
        assert names(PLATE_CONFIGURATION_DOC, "### Fields in phase 2") == list(service.PLATE_CONFIGURATION_FIELDS)
        assert names(PLATE_CONFIGURATION_DOC, "### A part in phase 2") == list(service.PART_FIELDS)
        assert names(PLATE_CONFIGURATION_DOC, "### An instance in phase 2") == list(service.INSTANCE_FIELDS)

    def test_the_limit_on_the_whole_plate_configuration(self):
        rows = {row[0].strip("`"): row[1] for row in table(PLATE_CONFIGURATION_DOC, "### Limits in phase 2")}
        assert rows["MAX_PLATE_CONFIGURATION_BYTES"].startswith(f"{limits.MAX_PLATE_CONFIGURATION_BYTES:,} ")

    def test_the_http_interfaces_codes_are_codes(self):
        named = set(re.findall(r"`(slice\.[a-z_]+)`", (CONTRACTS / "slice-http-interface.md").read_text()))
        built = {"slice.no_user_key", "slice.bad_request", "slice.bad_units", "slice.bad_plate_configuration",
                 "slice.part_missing", "slice.unknown_job", "slice.not_ready", "slice.file_gone"}
        assert built <= set(CODES) and built <= named

    def test_orientations_and_their_matrices(self):
        rows = table(PLATE_CONFIGURATION_DOC, "## Coordinates")
        documented = {row[0].strip("`"): ast.literal_eval(row[1].strip("`")) for row in rows}
        assert documented == plate.ORIENTATION_MATRICES

    def test_the_overrides_before_phase_2_are_the_examples_and_go_under_orcas_names(self):
        rows = table(PLATE_CONFIGURATION_DOC, "## Overrides")
        assert [row[0].strip("`") for row in rows] == list(OLD_OVERRIDES)
        assert set(json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text())["overrides"]) == set(OLD_OVERRIDES)

    def test_the_settings_in_phase_2_example_is_accepted(self):
        from penguin_slice.settings_table import validate_overrides
        block = re.search(r"```json\n(.*?)\n```", section(PLATE_CONFIGURATION_DOC, "### Settings in phase 2"), re.S)
        example = json.loads(block.group(1))
        assert validate_overrides(example) == example

    def test_limits(self):
        rows = table(PLATE_CONFIGURATION_DOC, "## Limits")
        for row in rows:
            name = row[0].strip("`")
            value = float(row[1].replace(",", ""))
            actual = getattr(limits, name, None)
            actual = getattr(plate, name) if actual is None else actual
            assert value == actual, name
        assert {row[0].strip("`") for row in rows} == {
            "MAX_INSTANCES", "MAX_PARTS", "MAX_PART_TRIANGLES", "MAX_PART_BYTES",
            "DEFAULT_MAX_PEAK_MB", "MIN_PART_EXTENT_MM", "MARGIN_MM", "SPACING_MM", "SPACING_SUPPORTS_MM",
            "PLATE_SLICE_TIMEOUT_S"}

    def test_memory_model_is_stated_with_the_codes_numbers(self):
        model = section(PLATE_CONFIGURATION_DOC, "### Memory")
        for name in ("MEMORY_BASE_MB", "MEMORY_PER_INSTANCE_MB", "MEMORY_PER_CM3_MB", "MEMORY_SUPPORTS_FACTOR"):
            assert f"`{name}` = {getattr(limits, name):g}" in model, name
        assert f"`{limits.MAX_PEAK_MB_ENV}`" in model

    def test_every_code_named_is_a_code(self):
        named = set(re.findall(r"`(slice\.[a-z_]+)`", PLATE_CONFIGURATION_DOC))
        assert named and named <= set(CODES)


class TestPlateConfigurationExample:
    def test_example_is_a_plate_configuration_the_service_accepts(self, tmp_path):
        configuration = example_parts(tmp_path).read(phase_2_of_the_example())
        assert [c["ref"] for c in configuration.instances] == ["bracket", "bracket", "spacer"]
        assert configuration.profiles.printer.name == "Bambu_Lab_H2S_0.4_nozzle.json"
        assert configuration.overrides == {"sparse_infill_density": "20%", "wall_loops": "3", "enable_support": "0",
                                           "brim_type": "auto_brim"}
        assert configuration.delivered_name == "Bracket_plus1-20261009-1432.gcode.3mf"

    def test_the_phase_2_example_names_the_examples_parts_by_hash(self):
        example = json.loads((CONTRACTS / "examples" / "plate-configuration-phase-2.json").read_text())
        assert list(example) == list(service.PLATE_CONFIGURATION_FIELDS)
        hashes = {sha256(p.read_bytes()) for p in EXAMPLE_PARTS.glob("*.stl")}
        assert {(p["sha256"] in hashes, p["units"]) for p in example["parts"].values()} == {(True, "mm")}

    def test_the_phase_2_example_is_the_example_with_a_fourth_instance(self):
        example = json.loads((CONTRACTS / "examples" / "plate-configuration-phase-2.json").read_text())
        built = phase_2_of_the_example()
        assert example["parts"] == built["parts"] and example["instances"][:3] == built["instances"]
        assert "rotation" in example["instances"][3]

    def test_example_parts_are_small(self):
        for part in json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text())["parts"].values():
            assert "/" not in part["stl"] and (EXAMPLE_PARTS / part["stl"]).stat().st_size < 2_000


class TestSlicedFile:
    @pytest.fixture
    def sliced(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        configuration = example_parts(tmp_path).read(phase_2_of_the_example())
        return slice_plate_configuration(configuration, tmp_path / "out")

    def test_summary_fields(self, sliced):
        assert names(SLICED_FILE_DOC, "## Summary") == list(service.SUMMARY_FIELDS) == list(sliced.summary)

    def test_example_matches_the_summary_the_code_writes(self, sliced):
        example = json.loads(SLICED_FILE_EXAMPLE.read_text())
        assert list(example) == list(sliced.summary)
        assert example["file"] == sliced.summary["file"] == sliced.path.name
        assert example["instances"] == sliced.summary["instances"]
        for key in ("print_time_s", "filament_m", "filament_g"):
            assert isinstance(example[key], float) and example[key] > 0, key
        assert isinstance(example["layer_count"], int) and example["layer_count"] > 0
        assert isinstance(example["warnings"], list)

    def test_contents_are_the_entries_the_code_reads(self, sliced):
        entries = names(SLICED_FILE_DOC, "## Contents")
        assert entries == [GCODE_ENTRY, SLICE_INFO_ENTRY, PLATE_JSON_ENTRY]
        with zipfile.ZipFile(sliced.path) as zf:
            assert set(entries) <= set(zf.namelist())

    def test_name_pattern_example(self):
        assert "`Bracket_plus1-20261009-1432.gcode.3mf`" in section(SLICED_FILE_DOC, "## Name")

    def test_the_summary_travels_in_no_header(self):
        assert "X-Slice-Summary" not in SLICED_FILE_DOC
        assert "`GET /slices/<job>/summary`" in SLICED_FILE_DOC


class TestIndex:
    def test_contracts_readme_links_both_documents(self):
        readme = (CONTRACTS / "README.md").read_text()
        assert "| Plate configuration | Wizard, through the front server | Slice service | "\
            "[plate-configuration.md](plate-configuration.md) |" \
            in readme
        assert "| Sliced file | Slice service | Front server, then printer delivery | [sliced-file.md](sliced-file.md) |" in readme

    def test_guide_lists_every_code(self):
        guide = (SLICE_ROOT / "README-details.md").read_text()
        listed = re.findall(r"^\| `(slice\.[a-z_]+)` \|", section(guide, "## Error codes"), re.M)
        assert listed == list(CODES)
