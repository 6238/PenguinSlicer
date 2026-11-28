"""print_config.py: the profile choice against the catalog, and the overrides written over
the process profile. No Orca run."""
import json
from unittest import mock

import pytest

from helpers import pinned_orca_version
from penguin_slice import print_config
from penguin_slice.print_config import (CHOOSE_PROFILES_MESSAGE, UNKNOWN_PRINTER_MESSAGE, Catalog, OverrideError,
                                        ProfileError,
                                        choose_profiles, default_names, load_catalog, printer_profile,
                                        validate_overrides, write_process_with_overrides)
from penguin_slice.slicer import DEFAULT_PROFILES

P4 = "Bambu Lab H2S 0.4 nozzle"
PLA = "Bambu PLA Basic @BBL H2S"
PETG_HF = "Bambu PETG HF @BBL H2S"
STANDARD = "0.20mm Standard @BBL H2S"
HIGH_QUALITY = "0.16mm High Quality @BBL H2S"
DEFAULTS = ("Bambu Lab H2S 0.6 nozzle", "Generic PETG @BBL H2S", "0.24mm Balanced Quality @BBL H2S 0.6 nozzle")


@pytest.fixture(scope="module")
def catalog():
    return Catalog.load()


class TestChooseProfiles:
    def test_default_names_come_from_the_default_files(self):
        assert default_names() == DEFAULTS

    @pytest.mark.parametrize("filament, process", [(None, None), (DEFAULTS[1], None), (None, DEFAULTS[2]),
                                                   DEFAULTS[1:]])
    def test_no_printer_is_the_default_set(self, catalog, filament, process):
        assert choose_profiles(None, filament, process, catalog) == DEFAULT_PROFILES

    @pytest.mark.parametrize("filament, process", [(PLA, None), (None, STANDARD), (PLA, STANDARD)])
    def test_default_set_refuses_other_profiles(self, catalog, filament, process):
        with pytest.raises(ProfileError) as caught:
            choose_profiles(None, filament, process, catalog)
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE
        assert caught.value.details.endswith("is not offered with the default set")

    def test_catalog_choice_gives_the_three_files(self, catalog):
        profiles = choose_profiles(P4, PETG_HF, HIGH_QUALITY, catalog)
        assert json.loads(profiles.printer.read_text())["name"] == P4
        assert json.loads(profiles.filament.read_text())["name"] == PETG_HF
        assert json.loads(profiles.process.read_text())["name"] == HIGH_QUALITY
        assert printer_profile(profiles)["name"] == P4

    @pytest.mark.parametrize("printer, shown", [("Bambu Lab H2Z 0.4 nozzle", "Bambu Lab H2Z 0.4 nozzle"),
                                                (7, "7")])
    def test_unknown_printer_fails_closed(self, catalog, printer, shown):
        with pytest.raises(ProfileError) as caught:
            choose_profiles(printer, PLA, STANDARD, catalog)
        assert caught.value.message == f"The printer '{shown}' is not one the slicer knows."
        assert caught.value.message == UNKNOWN_PRINTER_MESSAGE.format(name=shown)
        assert caught.value.error_code == "slice.unknown_printer"
        assert caught.value.details == f"printer {printer!r} is not in the catalog"
        assert isinstance(caught.value, ValueError)      # as the original refusal was

    @pytest.mark.parametrize("filament, process", [
        ("No Such Filament", STANDARD),                               # not in the catalog
        (PLA, "0.24mm Balanced Quality @BBL H2S 0.6 nozzle"),         # in the catalog, not for this printer
        (None, STANDARD), (PLA, None), (["list"], STANDARD),
    ])
    def test_filament_or_process_that_does_not_fit_is_refused(self, catalog, filament, process):
        with pytest.raises(ProfileError) as caught:
            choose_profiles(P4, filament, process, catalog)
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE
        assert caught.value.details == (f"filament {filament!r} or process {process!r} is not offered "
                                        f"for printer {P4!r}")

    def test_catalog_is_read_once_per_process(self):
        load_catalog.cache_clear()
        try:
            with mock.patch.object(Catalog, "load", wraps=Catalog.load) as spy:
                first = choose_profiles(P4, PLA, STANDARD)
                second = choose_profiles(P4, PLA, STANDARD)
            assert spy.call_count == 1
            assert first == second
        finally:
            load_catalog.cache_clear()

    def test_catalog_knows_its_orca_version_and_rejects_non_string_names(self, catalog):
        # The catalog was regenerated from the pinned Orca's own profiles.
        assert catalog.orca_version == pinned_orca_version()
        assert not catalog.has_printer(None)
        assert not catalog.compatible("filament", None, P4)

    def test_every_catalog_entry_has_its_file(self, catalog):
        index = json.loads((print_config.CATALOG_DIR / "index.json").read_text())
        for list_name in ("printers", "filaments", "processes"):
            assert index[list_name], list_name
            for entry in index[list_name]:
                data = json.loads((print_config.CATALOG_DIR / entry["file"]).read_text())
                assert data["name"] == entry["name"]


class TestOverrides:
    """The overrides' check is settings_table.py's (tests/test_settings_table.py); here, that
    the plate's checks use it and how the overrides are written over the process profile."""

    def test_the_plate_checks_take_the_table_check(self):
        from penguin_slice import settings_table
        assert validate_overrides is settings_table.validate_overrides
        assert OverrideError is settings_table.OverrideError

    def test_the_four_settings_as_built_are_refused_now(self):
        # Once the only overrides; now they are no setting of Orca's.
        with pytest.raises(OverrideError) as caught:
            validate_overrides({"infill": 20})
        assert caught.value.message == "The setting infill is not a print setting the slicer knows."

    def test_write_process_with_overrides(self, tmp_path):
        out = write_process_with_overrides(DEFAULT_PROFILES.process, {"wall_loops": "4"}, tmp_path / "process.json")
        assert out == tmp_path / "process.json"
        text = out.read_text()
        merged = json.loads(text)
        assert merged == dict(json.loads(DEFAULT_PROFILES.process.read_text()), wall_loops="4")
        assert list(merged) == sorted(merged) and text.endswith("}\n")
