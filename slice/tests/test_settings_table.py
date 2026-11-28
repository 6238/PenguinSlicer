"""settings_table.py: the checked-in table of settings (its contract's shape, what it holds
and leaves out) and every setting of it accepted in a plate configuration's `overrides`,
each value checked against its entry. No Orca run."""
import json

import pytest

from helpers import CONTRACTS
from penguin_slice import settings_table
from penguin_slice.print_config import load_catalog, write_process_with_overrides
from penguin_slice.settings_table import (CLASSIFICATION_PATH, TABLE_PATH, OverrideError, TableUnreadable, load,
                                          validate_overrides)
from penguin_slice.slicer import DEFAULT_PROFILES

EXAMPLE = CONTRACTS / "examples" / "settings-table.json"
FIELDS = {"name", "kind", "label", "section", "group", "explanation", "unit", "per_variant", "choices",
          "number_form", "min", "max", "max_length"}
FOR_KIND = {"choice": {"choices"}, "number": {"number_form"}, "text": {"max_length"}}
NOT_FOR_KIND = {"choice": {"number_form", "min", "max", "max_length"}, "number": {"choices", "max_length"},
                "text": {"choices", "number_form", "min", "max"}}


@pytest.fixture(scope="module")
def table():
    return json.loads(TABLE_PATH.read_text())


@pytest.fixture(scope="module")
def classification():
    return json.loads(CLASSIFICATION_PATH.read_text())


def entry_of(table, name):
    return next(e for e in table["settings"] if e["name"] == name)


class TestTheCheckedInTable:
    def test_its_head(self, table):
        assert table["format"] == 1 and table["orca_version"] == load_catalog().orca_version == "2.4.2"
        assert set(table) == {"format", "orca_version", "settings", "process_values", "catalog"}

    def test_every_entry_has_the_fields_of_its_kind_and_no_other(self, table):
        for entry in table["settings"]:
            assert set(entry) <= FIELDS, entry["name"]
            assert {"name", "kind", "label", "section", "group", "explanation", "per_variant"} <= set(entry)
            assert FOR_KIND[entry["kind"]] <= set(entry), entry["name"]
            assert not NOT_FOR_KIND[entry["kind"]] & set(entry), entry["name"]
            assert entry["label"] and entry["section"] and entry["group"], entry["name"]
            if entry["kind"] == "number":
                assert entry["number_form"] in {"integer", "decimal", "percent", "decimal_or_percent"}
            if entry["kind"] == "text":
                assert isinstance(entry["max_length"], int) and entry["max_length"] >= 1
            if entry["kind"] == "choice":
                assert entry["choices"] and all(set(c) == {"value", "label"} for c in entry["choices"])

    def test_an_on_and_off_setting_is_off_and_on(self, table):
        assert entry_of(table, "enable_support")["choices"] == [{"value": "0", "label": "Off"},
                                                                {"value": "1", "label": "On"}]

    def test_the_four_quick_changes_are_ordinary_settings(self, table):
        assert entry_of(table, "sparse_infill_density")["number_form"] == "percent"
        assert entry_of(table, "wall_loops")["number_form"] == "integer"
        assert "tree(auto)" in [c["value"] for c in entry_of(table, "support_type")["choices"]]
        assert {"auto_brim", "no_brim", "outer_only"} <= {c["value"] for c in entry_of(table, "brim_type")["choices"]}

    def test_every_process_profile_gives_every_setting_a_value(self, table):
        names = [e["name"] for e in table["settings"]]
        assert list(table["process_values"]) == [p["name"] for p in table["catalog"]["processes"]]
        for values in table["process_values"].values():
            assert list(values) == names and all(isinstance(v, str) for v in values.values())

    def test_every_process_profiles_own_value_fits_its_entry(self, table):
        # A profile's value put back by the user is left out of a plate configuration, yet a
        # configuration profile may name it: each must be accepted.
        for process, values in table["process_values"].items():
            assert validate_overrides(values) == {k: v for k, v in values.items()}, process

    def test_nothing_programmatic_and_nothing_of_a_filament_or_printer(self, table, classification):
        names = {e["name"] for e in table["settings"]}
        assert names == set(classification["parameters"])
        assert not names & set(classification["programmatic"]) and not names & set(classification["not_offered"])
        for profile in (DEFAULT_PROFILES.filament, DEFAULT_PROFILES.printer):
            own = set(json.loads(profile.read_text())) - {"name", "inherits", "compatible_printers", "from",
                                                          "setting_id", "version", "instantiation",
                                                          "compatible_printers_condition"}
            assert not names & own, profile.name
        assert {"post_process", "filename_format", "process_change_extrusion_role_gcode"} <= set(
            classification["programmatic"])

    def test_the_catalog_names_are_the_profile_catalogs(self, table):
        catalog = load_catalog()
        assert [p["name"] for p in table["catalog"]["printers"]] == catalog.printer_names()
        h2s = next(p for p in table["catalog"]["printers"] if p["name"] == "Bambu Lab H2S 0.6 nozzle")
        assert h2s == {"name": "Bambu Lab H2S 0.6 nozzle", "printable_area": [[0, 0], [340, 0], [340, 320], [0, 320]],
                       "printable_height": 340}
        assert len(table["catalog"]["filaments"]) == 136 and len(table["catalog"]["processes"]) == 16

    def test_the_contracts_example_has_the_real_tables_shape(self, table):
        """The example is shortened and written by hand: its settings are real ones of the same
        kind and form, its profiles real ones, and it has the real table's fields."""
        example = json.loads(EXAMPLE.read_text())
        assert set(example) == set(table) and example["format"] == table["format"]
        for entry in example["settings"]:
            real = entry_of(table, entry["name"])
            assert (entry["kind"], entry.get("number_form")) == (real["kind"], real.get("number_form")), entry["name"]
            assert set(entry) <= FIELDS
        assert set(example["process_values"]) <= set(table["process_values"])
        assert set(example["catalog"]) == set(table["catalog"])
        printer = example["catalog"]["printers"][0]
        assert printer == next(p for p in table["catalog"]["printers"] if p["name"] == printer["name"])

    def test_about_three_hundred_settings_in_a_few_hundred_kilobytes(self, table):
        assert len(table["settings"]) == 338
        assert len(TABLE_PATH.read_bytes()) < 500_000


def refused(overrides):
    with pytest.raises(OverrideError) as caught:
        validate_overrides(overrides)
    assert caught.value.error_code == "slice.bad_overrides"
    return caught.value


class TestAccepted:
    @pytest.mark.parametrize("name, value", [
        ("wall_loops", "4"),                                   # an integer
        ("layer_height", "0.24"),                              # a decimal
        ("outer_wall_speed", "200"),                           # a decimal written whole
        ("sparse_infill_density", "40%"),                      # a percent
        ("initial_layer_line_width", "0.62"),                  # either: a decimal
        ("initial_layer_line_width", "110%"),                  # either: a percent
        ("sparse_infill_pattern", "gyroid"),                   # a choice
        ("enable_support", "1"),                               # on and off
        ("support_type", "tree(auto)"),
        ("brim_type", "no_brim"),
        ("extra_solid_infills", "5"),                          # a text within its length
        ("sparse_infill_density", "0%"), ("sparse_infill_density", "100%"),    # the bounds themselves
        ("standby_temperature_delta", "-5"),                   # a negative integer within its range
    ])
    def test_a_setting_of_each_kind_and_form(self, name, value):
        assert validate_overrides({name: value}) == {name: value}

    def test_none_and_empty(self):
        assert validate_overrides(None) == {} and validate_overrides({}) == {}

    def test_the_four_quick_changes_together(self):
        quick = {"sparse_infill_density": "20%", "wall_loops": "3", "enable_support": "1", "support_type": "tree(auto)",
                 "brim_type": "auto_brim"}
        assert validate_overrides(quick) == quick


class TestRefused:
    def test_a_setting_the_table_does_not_hold(self):
        error = refused({"wall_lops": "3"})
        assert "wall_lops" in error.message and "not a print setting" in error.message
        assert "wall_lops" in error.details

    def test_a_programmatic_setting_names_why(self):
        error = refused({"post_process": "/bin/sh -c 'rm -rf /'"})
        assert error.message.startswith("The setting post_process cannot be changed: it runs a program")
        error = refused({"filename_format": "x.gcode"})
        assert "names a file on the server" in error.message
        error = refused({"process_change_extrusion_role_gcode": "M104 S300"})
        assert "custom G-code" in error.message

    def test_a_setting_orca_does_not_offer(self):
        error = refused({"travel_speed_z": "10"})
        assert error.message.startswith("The setting travel_speed_z cannot be changed: it is on no page")

    @pytest.mark.parametrize("name", ["nozzle_temperature", "machine_start_gcode", "printable_area", "nozzle_diameter"])
    def test_a_filament_or_printer_setting(self, name):
        error = refused({name: "1"})
        assert error.message == (f"The setting {name} belongs to the filament or printer profile, which a plate "
                                 f"cannot change.")

    def test_a_value_off_its_list(self):
        error = refused({"sparse_infill_pattern": "spiral"})
        assert error.message == ("Sparse infill pattern (Strength, Infill) cannot be 'spiral': choose one of the "
                                 "values Orca offers for it.")
        assert "sparse_infill_pattern" in error.details and "gyroid" in error.details

    def test_on_and_off_takes_only_0_and_1(self):
        for value in ("true", "on", "2", " 1"):
            assert "Enable support" in refused({"enable_support": value}).message

    @pytest.mark.parametrize("name, value, words", [
        ("wall_loops", "3.5", "a whole number"),
        ("wall_loops", "3e2", "a whole number"),
        ("wall_loops", "99999999999", "a whole number"),          # more than Orca's whole numbers hold
        ("layer_height", "0,24", "a number"),
        ("layer_height", "nan", "a number"),
        ("layer_height", "1e-3", "a number"),
        ("layer_height", "24%", "a number"),
        ("sparse_infill_density", "40", "a percentage such as 40%"),
        ("initial_layer_line_width", "0.6mm", "a number or a percentage"),
        ("layer_height", "", "a number"),
        ("layer_height", "1" * 41, "a number"),
        ("wall_loops", "٣", "a whole number"),                # an Arabic-Indic three: a digit, not Orca's
        ("layer_height", "0.٢", "a number"),
        ("wall_loops", "+3", "a whole number"),
        ("wall_loops", " 3", "a whole number"),
        ("layer_height", ".5", "a number"),
    ])
    def test_a_number_of_the_wrong_form(self, name, value, words):
        assert words in refused({name: value}).message

    def test_a_number_out_of_its_range(self):
        error = refused({"wall_loops": "1001"})
        assert error.message == "Wall loops (Strength, Walls) must be at most 1000, not 1001."
        error = refused({"sparse_infill_density": "-1%"})
        assert error.message == "Sparse infill density (Strength, Infill) must be at least 0%, not -1%."
        assert "below min 0" in error.details

    @pytest.mark.parametrize("name, value, words", [
        ("wall_loops", "-1", "must be at least 0, not -1."),                       # an integer
        ("layer_height", "-0.2", "must be at least 0, not -0.2."),                 # a decimal
        ("outer_wall_line_width", "-0.1", "must be at least 0, not -0.1."),        # a number or a percentage,
        ("outer_wall_line_width", "-1%", "must be at least 0, not -1%."),          # in each of its two forms
        ("outer_wall_line_width", "1000.5", "must be at most 1000, not 1000.5."),
        ("outer_wall_line_width", "5000%", "must be at most 1000, not 5000%."),
    ])
    def test_each_form_is_held_to_both_its_bounds(self, name, value, words):
        error = refused({name: value})
        assert error.message.endswith(words)
        assert ("below min" if "least" in words else "above max") in error.details

    @pytest.mark.parametrize("value", ["1000", "0", "1000%", "0%", "0.45"])
    def test_a_number_or_a_percentage_at_its_bounds_is_taken(self, value):
        assert validate_overrides({"outer_wall_line_width": value}) == {"outer_wall_line_width": value}

    def test_a_whole_number_below_what_orca_holds(self):
        assert "a whole number" in refused({"wall_loops": "-99999999999"}).message
        assert "a whole number" in refused({"wall_loops": str(-2 ** 31 - 1)}).message

    def test_a_text_one_character_over_its_length(self):
        entry = load().entries["extra_solid_infills"]
        error = refused({"extra_solid_infills": "5" * (entry["max_length"] + 1)})
        assert error.message == (f"Insert solid layers (Strength, Advanced) can be at most {entry['max_length']} "
                                 f"characters long.")

    def test_a_text_with_a_control_character(self):
        assert "line break" in refused({"extra_solid_infills": "\n"}).message

    def test_a_value_that_is_not_a_string(self):
        error = refused({"wall_loops": 3})
        assert error.message == "Wall loops (Strength, Walls) must be given as text, as Orca writes it, not 3."

    def test_overrides_that_are_not_an_object(self):
        assert "could not be read" in refused([1]).message
        assert "could not be read" in refused("wall_loops=3").message

    def test_the_first_problem_is_named_and_every_one_is_in_the_detail(self):
        error = refused({"wall_loops": "x", "nope": "1"})
        assert error.message.startswith("Wall loops") and "'nope'" in error.details

    def test_a_huge_value_is_cut_where_it_is_shown(self):
        error = refused({"sparse_infill_pattern": "x" * 5000})
        assert len(error.message) < 400 and len(error.details) < 2000

    def test_a_huge_name_is_cut_where_it_is_shown(self):
        error = refused({"n" * 5000: "1"})
        assert len(error.message) < 400

    def test_a_value_nested_too_deeply_is_named_as_such(self):
        deep = []
        for _ in range(100_000):
            deep = [deep]
        assert "a value nested too deeply" in refused({"wall_loops": deep}).message

    def test_many_problems_are_counted_past_twenty(self):
        error = refused({f"nope_{i}": "1" for i in range(25)})
        assert error.details.endswith("; and 5 more") and error.details.count("nope_") == 20

    def test_without_its_classification_or_profiles_a_refusal_still_names_the_setting(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings_table, "CLASSIFICATION_PATH", tmp_path / "gone.json")
        monkeypatch.setattr(settings_table, "PROFILE_DIR", tmp_path)
        settings_table._classification.cache_clear()
        settings_table._other_profiles_settings.cache_clear()
        try:
            for name in ("post_process", "nozzle_temperature"):
                assert refused({name: "1"}).message == f"The setting {name} is not a print setting the slicer knows."
        finally:
            settings_table._classification.cache_clear()
            settings_table._other_profiles_settings.cache_clear()


class TestPerVariant:
    """No setting of the pinned Orca is kept for each extruder variant (Orca reads a list
    given for a setting it holds once by its first value), so these use a table that says one is."""

    @pytest.fixture
    def variant_table(self, monkeypatch):
        real = load()
        entries = dict(real.entries)
        entries["outer_wall_speed"] = dict(entries["outer_wall_speed"], per_variant=True)
        monkeypatch.setattr(settings_table, "load", lambda: settings_table.Table(real.raw, {**real.data}, entries))

    def test_one_value_is_written_for_every_variant(self, variant_table, tmp_path):
        out = write_process_with_overrides(DEFAULT_PROFILES.process, {"outer_wall_speed": "150", "wall_loops": "4"},
                                           tmp_path / "process.json")
        written = json.loads(out.read_text())
        variants = json.loads(DEFAULT_PROFILES.process.read_text())["print_extruder_variant"]
        assert written["outer_wall_speed"] == ["150"] * len(variants) and len(variants) == 2
        assert written["wall_loops"] == "4"

    def test_a_profile_without_variants_gets_one(self, variant_table, tmp_path):
        process = tmp_path / "plain.json"
        process.write_text(json.dumps({"name": "plain"}))
        out = write_process_with_overrides(process, {"outer_wall_speed": "150"}, tmp_path / "process.json")
        assert json.loads(out.read_text())["outer_wall_speed"] == ["150"]


class TestUnreadable:
    def test_a_missing_table_is_the_servers_own_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings_table, "TABLE_PATH", tmp_path / "gone.json")
        settings_table.load.cache_clear()
        try:
            with pytest.raises(TableUnreadable) as caught:
                validate_overrides({"wall_loops": "3"})
            assert caught.value.error_code == "slice.profile_unreadable"
            assert caught.value.message == "The slicer could not read its table of settings."
            assert "gone.json" in caught.value.details
        finally:
            settings_table.load.cache_clear()

    def test_a_table_that_is_not_one(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"format": 1}')
        monkeypatch.setattr(settings_table, "TABLE_PATH", bad)
        settings_table.load.cache_clear()
        try:
            with pytest.raises(TableUnreadable):
                load()
        finally:
            settings_table.load.cache_clear()
