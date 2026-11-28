"""scripts/make_settings_table.py, the generator of the table of settings, run on a small
stand-in for Orca's source (tests/fixtures/orca_source/, written by hand in the form of
Orca's own files) and a small profile catalog (tests/fixtures/settings_catalog/)."""
import json
import shutil

import pytest

from helpers import FIXTURES
from make_settings_table import (TableError, build_table, cpp_string, main, read_definitions, read_enum_keys,
                                 read_pages, read_process_options, read_variant_options, strip_comments)

SOURCE = FIXTURES / "orca_source"
CATALOG = FIXTURES / "settings_catalog"
CLASSIFICATION = SOURCE / "classification.json"


def table(source=SOURCE, catalog=CATALOG, classification=CLASSIFICATION):
    return build_table(source, catalog, classification)


def entry(name, built=None):
    built = built or table()
    found = [e for e in built["settings"] if e["name"] == name]
    assert len(found) == 1, name
    return found[0]


class TestReadingTheSource:
    def test_comments_go_and_strings_stay(self):
        text = 'a("x // not a comment") // a comment\n/* "gone" */ b("y /* kept */")'
        assert strip_comments(text) == 'a("x // not a comment") \n  b("y /* kept */")'

    def test_a_string_expression_is_its_literals_joined(self):
        assert cpp_string('L("How tall " "each layer is.\\n" "Say \\"when\\".")', "x") == \
            'How tall each layer is.\nSay "when".'
        assert cpp_string('"%"', "x") == "%"
        assert cpp_string('L("a") + "b"', "x") == "ab"

    def test_a_string_built_by_code_is_refused_naming_the_setting(self):
        with pytest.raises(TableError, match="layer_height: cannot read .*format"):
            cpp_string('format(L("%1%"), 3)', "layer_height")

    def test_the_process_options_in_orcas_order_without_the_commented(self):
        text = (SOURCE / "src/libslic3r/Preset.cpp").read_text()
        assert read_process_options(text) == ["layer_height", "wall_loops", "infill_density", "first_line_width",
                                              "infill_pattern", "support_on", "solid_pattern", "wall_order",
                                              "outer_speed", "template_text", "ironing_inset", "end_gcode",
                                              "extruder_slots", "variant_speed", "inherits"]

    def test_the_options_kept_for_each_variant(self):
        text = (SOURCE / "src/libslic3r/PrintConfig.cpp").read_text()
        assert read_variant_options(text) == {"variant_speed", "extruder_slots"}

    def test_definitions_and_their_words(self):
        text = (SOURCE / "src/libslic3r/PrintConfig.cpp").read_text()
        defs = read_definitions(text)
        assert defs["layer_height"].type == "coFloat"
        assert defs["layer_height"].tooltip == "How tall each layer is. Smaller is finer."
        assert defs["infill_density"].tooltip == 'Density of the "sparse" infill, 100% is solid.'
        assert defs["outer_speed"].label == "Outer wall"
        assert (defs["wall_loops"].min, defs["wall_loops"].max) == (0, 1000)
        assert defs["first_line_width"].max is None
        assert (defs["outer_speed"].min, defs["outer_speed"].max) == (-1000, 1000)    # a named constant
        assert defs["bed_temperature"].problems == ["bed_temperature: cannot read its max 'bed_limit()'"]
        assert defs["infill_pattern"].enum_values == ["lines", "grid", "honeycomb"]
        # Choices taken over from another definition, and choices given as a list.
        assert defs["solid_pattern"].enum_values == ["lines", "grid", "honeycomb"]
        assert defs["solid_pattern"].enum_labels == ["Lines", "Grid", "Honeycomb"]
        assert defs["solid_pattern"].tooltip == "Line pattern of the infill."
        assert defs["wall_order"].enum_values == ["inner_outer", "outer_inner"]
        assert defs["wall_order"].enum_labels == ["Inner, then outer", "Outer, then inner"]
        assert defs["variant_speed"].type == "coFloats"
        assert "loop_a" not in defs                       # a key made by code names no definition
        assert defs["variant_speed"].label == "Variant speed"   # not "Made in a loop": the loop's lines are not its

    def test_the_enum_keys_by_constant(self):
        text = (SOURCE / "src/libslic3r/PrintConfig.cpp").read_text()
        assert read_enum_keys(text) == {"Pattern": {"ptLines": "lines", "ptGrid": "grid", "ptHidden": "hidden",
                                                    "ptHoneycomb": "honeycomb"},
                                        "WallOrder": {"woInnerOuter": "inner_outer", "woOuterInner": "outer_inner"}}

    def test_the_pages_and_groups_in_order(self):
        text = (SOURCE / "src/slic3r/GUI/Tab.cpp").read_text()
        assert read_pages(text) == [
            ("Quality", "Layer height", "layer_height"), ("Quality", "Line width", "first_line_width"),
            ("Strength", "Walls", "wall_loops"), ("Strength", "Walls", "wall_order"),
            ("Strength", "Infill", "infill_pattern"), ("Strength", "Infill", "infill_density"),
            ("Strength", "Infill", "template_text"), ("Strength", "Infill", "solid_pattern"),
            ("Speed", "Other layers speed", "outer_speed"), ("Speed", "Other layers speed", "variant_speed"),
            ("Support", "Support", "support_on"), ("Others", "End G-code", "end_gcode")]


class TestTheTable:
    def test_its_head_and_order(self):
        built = table()
        assert (built["format"], built["orca_version"]) == (1, "9.9.9")
        assert [e["name"] for e in built["settings"]] == ["layer_height", "first_line_width", "wall_loops",
                                                         "wall_order", "infill_pattern", "infill_density",
                                                         "template_text", "solid_pattern", "outer_speed",
                                                         "variant_speed", "support_on"]

    def test_a_decimal(self):
        assert entry("layer_height") == {
            "name": "layer_height", "kind": "number", "label": "Layer height", "section": "Quality",
            "group": "Layer height", "explanation": "How tall each layer is. Smaller is finer.", "unit": "mm",
            "per_variant": False, "number_form": "decimal", "min": 0}

    def test_an_integer_a_percent_and_either(self):
        assert entry("wall_loops")["number_form"] == "integer" and "unit" not in entry("wall_loops")
        assert (entry("wall_loops")["min"], entry("wall_loops")["max"]) == (0, 1000)
        assert entry("infill_density")["number_form"] == "percent" and entry("infill_density")["unit"] == "%"
        assert entry("first_line_width")["number_form"] == "decimal_or_percent"
        assert "max" not in entry("first_line_width")

    def test_a_choice_and_an_on_and_off(self):
        assert entry("infill_pattern")["choices"] == [{"value": "lines", "label": "Lines"},
                                                      {"value": "grid", "label": "Grid"},
                                                      {"value": "honeycomb", "label": "Honeycomb"}]
        assert entry("support_on")["choices"] == [{"value": "0", "label": "Off"}, {"value": "1", "label": "On"}]
        assert "number_form" not in entry("support_on") and "min" not in entry("support_on")

    def test_a_text_with_its_longest_value_and_no_explanation(self):
        text = entry("template_text")
        assert (text["kind"], text["max_length"], text["explanation"]) == ("text", 7, "")

    def test_a_text_never_shorter_than_one(self, tmp_path):
        catalog = tmp_path / "catalog"
        shutil.copytree(CATALOG, catalog)
        fine = json.loads((catalog / "process" / "Fine.json").read_text())
        fine["template_text"] = ""
        (catalog / "process" / "Fine.json").write_text(json.dumps(fine))
        assert entry("template_text", table(catalog=catalog))["max_length"] == 1

    def test_kept_for_each_variant(self):
        assert entry("variant_speed")["per_variant"] is True
        assert entry("variant_speed")["number_form"] == "decimal"
        assert entry("outer_speed")["per_variant"] is False

    def test_no_programmatic_and_no_unoffered_setting(self):
        names = {e["name"] for e in table()["settings"]}
        assert not names & {"end_gcode", "ironing_inset", "extruder_slots", "inherits", "bed_temperature"}

    def test_process_values_the_profiles_own_or_orcas_default(self):
        values = table()["process_values"]
        assert list(values) == ["0.16mm Fine @Test", "0.30mm Coarse @Test"]
        fine, coarse = values["0.16mm Fine @Test"], values["0.30mm Coarse @Test"]
        assert fine == {"layer_height": "0.16", "first_line_width": "0", "wall_loops": "3",
                        "wall_order": "inner_outer", "infill_pattern": "grid", "infill_density": "20%",
                        "template_text": "0,90,45", "solid_pattern": "lines",
                        # A list for a setting Orca holds once: Orca reads its first value.
                        "outer_speed": "120",
                        # Kept for each variant: the High Flow variant of the profile's printer.
                        "variant_speed": "45", "support_on": "0"}
        assert coarse["wall_loops"] == "2" and coarse["infill_density"] == "15%" and coarse["support_on"] == "1"
        assert coarse["infill_pattern"] == "grid" and coarse["outer_speed"] == "60" and coarse["variant_speed"] == "50"
        assert coarse["template_text"] == ""

    def test_the_catalog_names(self):
        catalog = table()["catalog"]
        assert catalog["printers"] == [{"name": "Test Printer 0.6 nozzle",
                                        "printable_area": [[0, 0], [250.5, 0], [250.5, 210], [0, 210]],
                                        "printable_height": 220}]
        assert catalog["filaments"] == [{"name": "Test PLA", "printers": ["Test Printer 0.6 nozzle"]}]
        assert catalog["processes"] == [{"name": "0.16mm Fine @Test", "printers": ["Test Printer 0.6 nozzle"]},
                                        {"name": "0.30mm Coarse @Test", "printers": ["Test Printer 0.6 nozzle"]}]


def edited_classification(tmp_path, change):
    data = json.loads(CLASSIFICATION.read_text())
    change(data)
    path = tmp_path / "classification.json"
    path.write_text(json.dumps(data))
    return path


class TestRefusals:
    def test_a_setting_classified_nowhere_fails_naming_it(self, tmp_path):
        path = edited_classification(tmp_path, lambda d: d["parameters"].remove("wall_loops"))
        with pytest.raises(TableError, match=r"classified nowhere.*wall_loops"):
            table(classification=path)

    def test_a_classified_setting_orca_no_longer_has_fails_naming_it(self, tmp_path):
        path = edited_classification(tmp_path, lambda d: d["programmatic"].update(old_gcode="custom G-code"))
        with pytest.raises(TableError, match=r"not a process setting of this Orca.*old_gcode"):
            table(classification=path)

    def test_a_setting_classified_twice_fails_naming_it(self, tmp_path):
        path = edited_classification(tmp_path, lambda d: d["not_offered"].update(wall_loops="twice"))
        with pytest.raises(TableError, match=r"classified more than once.*wall_loops"):
            table(classification=path)

    def test_a_programmatic_setting_needs_its_reason(self, tmp_path):
        path = edited_classification(tmp_path, lambda d: d["programmatic"].update(end_gcode=""))
        with pytest.raises(TableError, match=r"end_gcode: no reason"):
            table(classification=path)

    def test_a_parameter_on_no_page_fails(self, tmp_path):
        def change(d):
            d["not_offered"].pop("ironing_inset")
            d["parameters"].append("ironing_inset")
        with pytest.raises(TableError, match=r"ironing_inset: on no page of Orca's process settings"):
            table(classification=edited_classification(tmp_path, change))

    def test_a_list_not_kept_for_each_variant_fails(self, tmp_path, monkeypatch):
        import make_settings_table
        monkeypatch.setattr(make_settings_table, "read_variant_options", lambda text: set())
        with pytest.raises(TableError, match=r"variant_speed: a list of values"):
            table()

    def test_a_parameter_without_a_definition_fails(self, tmp_path):
        def change(d):
            d["not_offered"].pop("inherits")
            d["parameters"].append("inherits")
        with pytest.raises(TableError, match=r"inherits: no definition"):
            table(classification=edited_classification(tmp_path, change))

    def test_a_missing_source_file_names_it(self, tmp_path):
        with pytest.raises(TableError, match=r"cannot read .*Preset.cpp.*make -C slice orca-source"):
            table(source=tmp_path)

    def test_a_variant_the_process_does_not_list_fails(self, tmp_path):
        catalog = tmp_path / "catalog"
        shutil.copytree(CATALOG, catalog)
        printer_file = catalog / "printer" / "Test_Printer_0.6_nozzle.json"
        printer = json.loads(printer_file.read_text())
        printer["nozzle_volume_type"] = ["Hardened"]
        printer_file.write_text(json.dumps(printer))
        with pytest.raises(TableError, match=r"0.16mm Fine @Test.*Direct Drive Hardened"):
            table(catalog=catalog)


class TestMain:
    def test_writes_the_table(self, tmp_path):
        out = tmp_path / "table.json"
        assert main(["--source", str(SOURCE), "--catalog", str(CATALOG), "--classification", str(CLASSIFICATION),
                     "--out", str(out)]) == 0
        assert json.loads(out.read_text()) == table()

    def test_check_passes_on_the_same_table_and_fails_on_another(self, tmp_path, capsys):
        out = tmp_path / "table.json"
        args = ["--source", str(SOURCE), "--catalog", str(CATALOG), "--classification", str(CLASSIFICATION),
                "--out", str(out)]
        main(args)
        assert main(args + ["--check"]) == 0
        out.write_text("{}")
        assert main(args + ["--check"]) == 1
        assert "differs from what the generator makes" in capsys.readouterr().err

    def test_a_refusal_is_printed_and_exits_1(self, tmp_path, capsys):
        assert main(["--source", str(tmp_path), "--catalog", str(CATALOG), "--classification",
                     str(CLASSIFICATION), "--out", str(tmp_path / "t.json")]) == 1
        assert "make-settings-table:" in capsys.readouterr().err
