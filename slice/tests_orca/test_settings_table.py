"""The upstream check of the table of settings: the pinned Orca's source (tools/orca-source,
fetched by `make orca-source`, which `make test-upstream` runs first) has no process setting
classified nowhere, the checked-in table is what the generator makes from it, and the real
Orca slices with the table's process values and with every kind of override as sent."""
import json
import zipfile

import pytest

from helpers import PLATE_ID, SUBMISSION_ID, pinned_orca_version, sha256
from make_settings_table import SOURCE_DIR, SOURCE_FILES, TableError, build_table, dumps, read_process_options
from penguin_slice.settings_table import CLASSIFICATION_PATH, TABLE_PATH
from penguin_slice.slicer import SAMPLE_STL
from test_orca import through_the_http_interface

H2S_06 = "Bambu Lab H2S 0.6 nozzle"
# One of each kind and number form, each a value no catalog process gives (wall loops 5, ...).
OVERRIDES = {"wall_loops": "5", "layer_height": "0.28", "sparse_infill_density": "35%",
             "initial_layer_line_width": "120%", "outer_wall_line_width": "0.65", "sparse_infill_pattern": "gyroid",
             "enable_support": "1", "support_type": "tree(auto)", "brim_type": "no_brim", "extra_solid_infills": "7"}


def test_the_source_is_the_pinned_versions():
    """Protects: the table is read from the source of the Orca version that is pinned."""
    stamp = (SOURCE_DIR / "VERSION").read_text().split()
    assert stamp[0] == pinned_orca_version(), "run `make -C slice orca-source`"
    for rel in SOURCE_FILES.values():
        assert (SOURCE_DIR / rel).is_file(), rel


def test_every_setting_of_the_pinned_orca_is_classified():
    """Protects: no process setting of the pinned Orca is accepted or offered without someone
    having classified it (src/penguin_slice/settings/classification.json)."""
    options = read_process_options((SOURCE_DIR / SOURCE_FILES["options"]).read_text())
    classification = json.loads(CLASSIFICATION_PATH.read_text())
    classified = set(classification["parameters"]) | set(classification["programmatic"]) | set(
        classification["not_offered"])
    unclassified = [name for name in options if name not in classified]
    assert unclassified == [], f"classify these new process settings in {CLASSIFICATION_PATH}: {unclassified}"
    assert sorted(classified - set(options)) == [], "classified, but no process setting of this Orca"


def test_the_checked_in_table_is_what_the_generator_makes():
    """Protects: the checked-in table (src/penguin_slice/settings/table.json) is the one the
    generator makes from the pinned Orca's source and the profile catalog."""
    try:
        made = dumps(build_table())
    except TableError as exc:
        pytest.fail(f"the generator cannot make the table: {exc}")
    assert made == TABLE_PATH.read_text(), "run `make -C slice settings-table` and review the diff"


def _value(text):
    """A value as Orca writes it, for comparing: its first when a list, a number as a number."""
    if isinstance(text, list):
        text = text[0] if text else ""
    try:
        return float(text.rstrip("%")), text.endswith("%")
    except (ValueError, AttributeError):
        return text


@pytest.mark.parametrize("process, overrides", [
    ("0.24mm Balanced Quality @BBL H2S 0.6 nozzle", {}),
    # Its speeds differ for the two extruder variants: Orca slices with the first (Standard) value.
    ("0.30mm Standard @BBL H2S 0.6 nozzle", OVERRIDES),
])
def test_orca_slices_with_the_tables_values_and_the_overrides(tmp_path, process, overrides):
    """Protects: the table's process values are what Orca slices with when nothing replaces
    them (each profile's own value, Orca's default for the rest, a list's first value), and
    each override of each kind reaches Orca as sent; both read from the settings Orca writes
    into the sliced file (Metadata/project_settings.config)."""
    table = json.loads(TABLE_PATH.read_text())
    data = SAMPLE_STL.read_bytes()
    configuration = {"plate_id": PLATE_ID, "submission_id": SUBMISSION_ID,
                     "parts": {"b": {"name": "Bracket", "sha256": sha256(data), "units": "mm"}},
                     "instances": [{"ref": "b", "orientation": "+z", "angle": 0, "x": 150.0, "y": 150.0}],
                     "printer": H2S_06, "filament": "Generic PETG @BBL H2S", "process": process,
                     "overrides": overrides}
    _stages, report, sliced, summary = through_the_http_interface(tmp_path / "work", configuration, [data])
    assert report["state"] == "done", report
    (tmp_path / "plate.gcode.3mf").write_bytes(sliced)
    with zipfile.ZipFile(tmp_path / "plate.gcode.3mf") as zf:
        used = json.loads(zf.read("Metadata/project_settings.config"))
    expected = dict(table["process_values"][process], **overrides)
    differ = {name: (value, used.get(name)) for name, value in expected.items()
              if name not in used or _value(used[name]) != _value(value)}
    print(f"\n[orca] {process}: {len(expected)} settings compared, {len(overrides)} overridden; differ: {differ}")
    assert differ == {}
