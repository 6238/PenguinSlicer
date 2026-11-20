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

from helpers import CONTRACTS, SLICE_ROOT, install_fake_orca
from penguin_slice import limits, plate, service
from penguin_slice.errors import CODES
from penguin_slice.print_config import OVERRIDE_CHOICES
from penguin_slice.service import read_plate_configuration, slice_plate_configuration
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


class TestPlateConfigurationDocument:
    def test_fields(self):
        assert names(PLATE_CONFIGURATION_DOC, "## Fields") == list(service.PLATE_CONFIGURATION_FIELDS)
        assert names(PLATE_CONFIGURATION_DOC, "### Part") == list(service.PART_FIELDS)
        assert names(PLATE_CONFIGURATION_DOC, "### Instance") == list(service.INSTANCE_FIELDS)

    def test_orientations_and_their_matrices(self):
        rows = table(PLATE_CONFIGURATION_DOC, "## Coordinates")
        documented = {row[0].strip("`"): ast.literal_eval(row[1].strip("`")) for row in rows}
        assert documented == plate.ORIENTATION_MATRICES

    def test_overrides(self):
        rows = table(PLATE_CONFIGURATION_DOC, "## Overrides")
        documented = {row[0].strip("`"): [ast.literal_eval(v.strip()) for v in row[1].replace("`", "").split(",")]
                      for row in rows}
        assert documented == OVERRIDE_CHOICES

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
            "DEFAULT_MAX_PEAK_MB", "MIN_PART_EXTENT_MM", "MARGIN_MM", "SPACING_MM", "PLATE_SLICE_TIMEOUT_S"}

    def test_memory_model_is_stated_with_the_codes_numbers(self):
        model = section(PLATE_CONFIGURATION_DOC, "### Memory")
        for name in ("MEMORY_BASE_MB", "MEMORY_PER_INSTANCE_MB", "MEMORY_PER_CM3_MB", "MEMORY_SUPPORTS_FACTOR"):
            assert f"`{name}` = {getattr(limits, name):g}" in model, name
        assert f"`{limits.MAX_PEAK_MB_ENV}`" in model

    def test_every_code_named_is_a_code(self):
        named = set(re.findall(r"`(slice\.[a-z_]+)`", PLATE_CONFIGURATION_DOC))
        assert named and named <= set(CODES)


class TestPlateConfigurationExample:
    def test_example_is_a_plate_configuration_the_service_accepts(self):
        configuration = read_plate_configuration(json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text()), EXAMPLE_PARTS,
                                                 confine_to=EXAMPLE_PARTS)
        assert [c["ref"] for c in configuration.instances] == ["bracket", "bracket", "spacer"]
        assert configuration.profiles.printer.name == "Bambu_Lab_H2S_0.4_nozzle.json"
        assert configuration.overrides == {"sparse_infill_density": "20%", "wall_loops": "3", "enable_support": "0",
                                           "brim_type": "auto_brim"}
        assert configuration.delivered_name == "Bracket_plus1-20261009-1432.gcode.3mf"

    def test_example_uses_every_field(self):
        data = json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text())
        assert list(data) == list(service.PLATE_CONFIGURATION_FIELDS)
        assert set(data["overrides"]) == set(OVERRIDE_CHOICES)

    def test_example_parts_are_small(self):
        for part in json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text())["parts"].values():
            assert "/" not in part["stl"] and (EXAMPLE_PARTS / part["stl"]).stat().st_size < 2_000


class TestSlicedFile:
    @pytest.fixture
    def sliced(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        return slice_plate_configuration(json.loads(PLATE_CONFIGURATION_EXAMPLE.read_text()), tmp_path / "out",
                                         base_dir=EXAMPLE_PARTS)

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
        assert "| Plate configuration | Wizard | Slice service | [plate-configuration.md](plate-configuration.md) |" \
            in readme
        assert "| Sliced file | Slice service | Printer delivery | [sliced-file.md](sliced-file.md) |" in readme

    def test_guide_lists_every_code(self):
        guide = (SLICE_ROOT / "README.md").read_text()
        listed = re.findall(r"^\| `(slice\.[a-z_]+)` \|", section(guide, "## Error codes"), re.M)
        assert listed == list(CODES)
