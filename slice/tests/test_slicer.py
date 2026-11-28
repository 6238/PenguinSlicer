"""slicer.py: the command lines, Orca's isolation, how its failures are read, and the
summary. Orca is never run: slicer.run_process is replaced, or the binary is a placeholder.
tests/test_orca_runner.py runs run_process itself on fake_orca.py."""
import json
import os
import shutil
import signal
import struct
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from helpers import FIXTURES, corrupt_entry, make_archive
from penguin_slice import limits
from penguin_slice import slicer
from penguin_slice.slicer import (OrcaExit, SliceCancelled, SliceError, build_command, part_info, read_summary,
                                  slice_stl, stl_bounds)


TOO_CLOSE = "Two instances are too close together: the slicer found that their paths would meet."
LOG_LINE = "cli_status_callback: percent=-1, warning_step=7, message={}, message_type=2, flag=32\n"


def fake_run_factory(returncode=0, write_archive=True, write_result_json=True, stdout="log line", stopped=None,
                     result=None):
    """A stand-in for slicer.run_process that writes what Orca writes and returns its exit."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        outdir = Path(cmd[cmd.index("--outputdir") + 1])
        name = cmd[cmd.index("--export-3mf") + 1]
        if write_archive:
            make_archive(outdir / name)
            if name == slicer.PLATE_ARCHIVE:         # a plate's sliced file has its objects' list
                with zipfile.ZipFile(outdir / name, "a") as zf:
                    zf.writestr(slicer.PLATE_JSON_ENTRY, '{"bbox_objects": []}')
        if result is not None:
            (outdir / "result.json").write_text(result if isinstance(result, str) else json.dumps(result))
        elif write_result_json:
            shutil.copy(FIXTURES / "result.json", outdir / "result.json")
        return OrcaExit(returncode, stdout, stopped=stopped, memory_peak_kb=1234, wall_s=0.5)

    fake_run.calls = calls
    return fake_run


def fake_result_run(returncode, return_code=None, error_string="x", warning=None, stdout="orca says no"):
    """A stand-in that writes no archive, and a result.json carrying `return_code` unless None."""
    result = None
    if return_code is not None:
        result = {"return_code": return_code, "error_string": error_string}
        if warning is not None:
            result["sliced_plates"] = [{"id": 1, "warning_message": warning}]
    return fake_run_factory(returncode, write_archive=False, write_result_json=False, stdout=stdout, result=result)


@pytest.fixture
def out(tmp_path):
    # .resolve(): the slice functions resolve their arguments, and on macOS /tmp is a
    # symlink, so an unresolved path would not compare equal.
    return tmp_path.resolve() / "out"


@pytest.fixture
def executable_orca(tmp_path, monkeypatch):
    """A binary that exists (it never runs: run_process is replaced)."""
    path = tmp_path / "orca-present"
    path.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setenv(slicer.ORCA_ENV, str(path))
    return path


def patched(fake):
    return mock.patch.object(slicer, "run_process", fake)


class TestOrcaLocation:
    def test_environment_variable_names_the_binary(self, monkeypatch, tmp_path):
        monkeypatch.setenv(slicer.ORCA_ENV, str(tmp_path / "elsewhere" / "orca"))
        assert slicer.orca_bin() == tmp_path / "elsewhere" / "orca"

    def test_default_is_tools_orca_in_the_slice_project(self, monkeypatch):
        monkeypatch.delenv(slicer.ORCA_ENV)
        assert slicer.orca_bin() == slicer.SLICE_ROOT / "tools" / "orca" / "orca-slicer"
        assert (slicer.SLICE_ROOT / "pyproject.toml").is_file()

    def test_missing_binary_refuses_before_running_anything(self, monkeypatch, tmp_path, out):
        monkeypatch.setenv(slicer.ORCA_ENV, str(tmp_path / "no-such-orca"))
        fake = fake_run_factory()
        with patched(fake), pytest.raises(RuntimeError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert str(caught.value) == f"Orca Slicer is missing at {tmp_path / 'no-such-orca'}; run `make install`"
        assert fake.calls == []

    def test_import_does_not_need_orca(self, monkeypatch, tmp_path):
        monkeypatch.setenv(slicer.ORCA_ENV, str(tmp_path / "no-such-orca"))
        assert slicer.build_command(slicer.SAMPLE_STL, tmp_path)[0] == str(tmp_path / "no-such-orca")


class TestSampleCommand:
    def test_command_uses_binary_default_profiles_and_flags(self, out, placeholder_orca):
        cmd = build_command(slicer.SAMPLE_STL, out)
        assert cmd == [
            str(placeholder_orca),
            "--debug", "3", "--logfile", str(out / "orca.log"),
            "--datadir", str(out / "datadir"),
            "--load-settings", f"{slicer.PROFILE_DIR / 'printer.json'};{slicer.PROFILE_DIR / 'process.json'}",
            "--load-filaments", str(slicer.PROFILE_DIR / "filament.json"),
            "--arrange", "1",
            "--slice", "0",
            "--pipe", str(out / "orca-progress.fifo"),
            "--export-3mf", "sample_part.gcode.3mf",
            "--outputdir", str(out),
            str(slicer.SAMPLE_STL),
        ]

    def test_relative_paths_are_resolved_to_absolute(self):
        cmd = build_command(Path("parts/sample_part.stl"), Path("out"))
        assert cmd[-1] == str(Path("parts/sample_part.stl").resolve())
        assert cmd[cmd.index("--outputdir") + 1] == str(Path("out").resolve())
        for token in cmd:
            for piece in token.split(";"):
                if "/" in piece:
                    assert Path(piece).is_absolute(), piece
        assert cmd[cmd.index("--export-3mf") + 1] == "sample_part.gcode.3mf"


class TestSliceStl:
    def test_slice_creates_output_dir_and_isolated_environment(self, out, monkeypatch, executable_orca):
        monkeypatch.setenv("SLICE_SECRET_MARKER", "x")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("HOME", "/home/someone")
        fake = fake_run_factory()
        with patched(fake):
            result = slice_stl(slicer.SAMPLE_STL, out)
        assert out.is_dir()
        cmd, kwargs = fake.calls[0]
        env = kwargs["env"]
        # The caller's environment may hold secrets; Orca sees an allowlist and its own HOME.
        assert "SLICE_SECRET_MARKER" not in env
        assert slicer.ORCA_ENV not in env
        assert set(env) <= set(slicer.ENV_ALLOWLIST) | {"HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "LC_ALL"}
        assert env["PATH"] == "/usr/bin:/bin"
        assert env["HOME"] == str(out / "home")
        assert env["XDG_CONFIG_HOME"] == str(out / "xdg-config")
        assert env["XDG_RUNTIME_DIR"] == str(out / "xdg-runtime")
        assert env["LC_ALL"] == "C"
        assert (out / "xdg-runtime").stat().st_mode & 0o777 == 0o700
        assert kwargs["cwd"] == out
        assert kwargs["timeout_s"] == slicer.DEFAULT_TIMEOUT_S == 120
        assert kwargs["progress_fifo"] == out / "orca-progress.fifo"
        assert result.output_path == out / "sample_part.gcode.3mf"
        assert (result.peak_rss_kb, result.wall_s) == (1234, 0.5)

    def test_summary_from_archive_and_result_json(self, out, executable_orca):
        with patched(fake_run_factory()):
            result = slice_stl(slicer.SAMPLE_STL, out)
        assert result.summary() == {"print_time_s": 790.0, "filament_m": 1.09, "filament_g": 3.31,
                                    "layer_count": 50, "warnings": []}

    def test_nonzero_exit_raises_with_code_and_last_lines(self, out, executable_orca):
        stdout = "\n".join(f"line {i}" for i in range(30))
        with patched(fake_run_factory(returncode=1, write_archive=False, write_result_json=False, stdout=stdout)):
            with pytest.raises(SliceError) as caught:
                slice_stl(slicer.SAMPLE_STL, out)
        details = caught.value.details.splitlines()
        assert details[0] == "exit code 1"
        assert details[1:] == [f"line {i}" for i in range(11, 30)]
        assert caught.value.message == "The slicer could not slice this plate."
        assert caught.value.code is None

    def test_unstartable_slicer(self, out, executable_orca):
        def boom(cmd, **kwargs):
            raise OSError(8, "Exec format error", cmd[0])

        with patched(boom), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert (caught.value.error_code, caught.value.message) == ("slice.orca_unstartable",
                                                                   "The slicer could not be started.")
        assert "Exec format error" in caught.value.details

    def test_placeholder_binary_is_unstartable_without_mocking(self, out):
        # The suite's safety net: the real run_process on the non-executable placeholder.
        with pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.message == "The slicer could not be started."
        assert "Permission denied" in caught.value.details
        assert not (out / "orca-progress.fifo").exists()

    def test_timeout_keeps_what_orca_printed(self, out, executable_orca):
        fake = fake_run_factory(write_archive=False, stdout="still slicing", stopped="timeout")
        with patched(fake), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out, timeout_s=7)
        assert (caught.value.error_code, caught.value.message) == ("slice.timeout",
                                                                   "The slicer took too long on this plate.")
        assert caught.value.code == "timeout"
        assert caught.value.details == ("stopped by the slice service (timeout) with SIGTERM after 0.5 s\n"
                                        "still slicing")
        assert fake.calls[0][1]["timeout_s"] == 7

    @pytest.mark.parametrize("reason", ["cancel", "replaced", "shutdown", "requested"])
    def test_a_stop_that_is_not_the_timeout_is_a_cancel(self, out, executable_orca, reason):
        with patched(fake_run_factory(write_archive=False, stopped=reason)), pytest.raises(SliceCancelled) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.details == f"stopped by the slice service ({reason}) with SIGTERM after 0.5 s"

    def test_missing_archive_after_exit_zero(self, out, executable_orca):
        stdout = "\n".join(f"line {i}" for i in range(25))
        with patched(fake_run_factory(write_archive=False, stdout=stdout)), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.error_code == "slice.no_output"
        assert caught.value.details.splitlines() == [f"line {i}" for i in range(5, 25)]

    def test_scratch_that_cannot_be_written(self, tmp_path, executable_orca):
        blocker = tmp_path / "a-file"
        blocker.write_text("not a folder")
        with patched(fake_run_factory()), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, blocker / "out")
        assert caught.value.error_code == "slice.scratch_unwritable"
        assert "a-file" in caught.value.details


class TestReadSummary:
    def test_warnings_come_from_result_json(self, out):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == []     # macOS writes no result.json
        data = json.loads((FIXTURES / "result.json").read_text())
        data["sliced_plates"][0]["warning_message"] = "  Object is out of the bed \n"
        data["sliced_plates"].append({"warning_message": None})
        (out / "result.json").write_text(json.dumps(data))
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == ["Object is out of the bed"]

    @pytest.mark.parametrize("content", ["{not json", "[1, 2]", '"text"', "null", '{"sliced_plates": "none"}',
                                         '{"sliced_plates": ["warning", 3, null]}',
                                         '{"sliced_plates": [{"warning_message": 7}, {"warning_message": ["a"]}]}',
                                         b'{"sliced_plates": [{"warning_message": ""}]}\xff',
                                         "[" * 100_000])
    def test_result_json_of_any_shape_gives_no_warnings_and_keeps_the_slice(self, out, content):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        if isinstance(content, bytes):
            (out / "result.json").write_bytes(content)
        else:
            (out / "result.json").write_text(content)
        summary = read_summary(out / "x.gcode.3mf", out)
        assert summary["warnings"] == []
        assert summary["layer_count"] == 50

    def test_every_warning_in_the_debug_log_is_kept_once_in_one_order(self, out):
        """The pinned Orca's result.json keeps one warning of a plate, a different one from
        run to run (the real parts' mixed plate); its debug log has them all, in the order
        its threads reached them. The summary gives each once, sorted with the instance
        numbers read as numbers (#2 before #10), the same every time."""
        import fake_orca
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        data = json.loads((FIXTURES / "result.json").read_text())
        data["sliced_plates"][0]["warning_message"] = "It seems object Block #10 has floating cantilever."
        (out / "result.json").write_text(json.dumps(data))
        names = ["Pulley #2", "Block #10", "Block #2", "Pulley #2", "Block #1"]
        (out / slicer.ORCA_LOG).write_text("".join(fake_orca.LOG_WARNING.format(name=n) + "\n" for n in names))
        regions = "has floating regions. Please re-orient the object or enable support generation."
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == [
            f"It seems object Block #1 {regions}", f"It seems object Block #2 {regions}",
            "It seems object Block #10 has floating cantilever.", f"It seems object Block #10 {regions}",
            f"It seems object Pulley #2 {regions}"]

    def test_the_warnings_of_a_plate_are_bounded(self, out, monkeypatch):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        line = "cli_status_callback: percent=-1, warning_step=7, message=warning {}, message_type=2, flag=32\n"
        (out / slicer.ORCA_LOG).write_text("".join(line.format(i) for i in range(12)))
        monkeypatch.setattr(slicer, "MAX_PLATE_WARNINGS", 10)
        found = read_summary(out / "x.gcode.3mf", out)["warnings"]
        assert found == [f"warning {i}" for i in range(10)]

    def test_a_long_warning_in_both_sources_is_listed_once(self, out):
        """result.json and the debug log go through one normaliser: a warning over
        MAX_WARNING_CHARS is cut alike in both, so it is one warning, not two."""
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        long = "It seems object Block #1 has " + "a very long reason " * 30
        (out / "result.json").write_text(json.dumps({"sliced_plates": [{"warning_message": f" {long} "}]}))
        (out / slicer.ORCA_LOG).write_text(LOG_LINE.format(long))
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == [long.strip()[:slicer.MAX_WARNING_CHARS]]

    def test_a_run_of_thousands_of_digits_neither_fails_nor_misorders(self, out):
        """Python refuses int() of a run over 4,300 digits; the sort key never converts."""
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        (out / "result.json").write_text(json.dumps({"sliced_plates": [{"warning_message": "9" * 5000}]}))
        (out / slicer.ORCA_LOG).write_text(LOG_LINE.format("8" * 299) + LOG_LINE.format("10"))
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == ["10", "8" * 299, "9" * 300]
        assert sorted(["9" * 5000, "1" + "0" * 5000, "007"], key=slicer._natural) == ["007", "9" * 5000,
                                                                                        "1" + "0" * 5000]

    @pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 0, 2), (2, 0, 1)])
    def test_warnings_that_differ_only_in_leading_zeros_come_in_one_order(self, out, order):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        texts = ["Block 7", "Block 007", "Block 07"]
        (out / slicer.ORCA_LOG).write_text("".join(LOG_LINE.format(texts[i]) for i in order))
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == ["Block 007", "Block 07", "Block 7"]
        # A strict order, so no tie is left to the order of a set (which PYTHONHASHSEED sets).
        assert slicer._natural("Block 007") < slicer._natural("Block 07") < slicer._natural("Block 7")

    def test_past_the_bound_the_warnings_kept_are_the_first_in_order_not_the_first_logged(self, out, monkeypatch):
        """Which warnings a long list keeps must not depend on the order Orca's threads logged
        them in: the whole log is read and the first MAX_PLATE_WARNINGS in order are kept."""
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        monkeypatch.setattr(slicer, "MAX_PLATE_WARNINGS", 10)
        for order in (range(35), reversed(range(35))):
            (out / slicer.ORCA_LOG).write_text("".join(LOG_LINE.format(f"warning {i}") for i in order))
            assert read_summary(out / "x.gcode.3mf", out)["warnings"] == [f"warning {i}" for i in range(10)]

    def test_the_pairs_orca_found_too_close_are_read_in_one_order_and_bounded(self, out, monkeypatch):
        out.mkdir()
        monkeypatch.setattr(slicer, "MAX_PLATE_WARNINGS", 3)          # the reader's bound, to reach it
        lines = [f"gcode path conflicts found between Block #{i + 1} and Block #{i}\n" for i in range(12, 0, -1)]
        (out / slicer.ORCA_LOG).write_text("noise\n" + "".join(lines + lines) + "gcode path conflicts found between "
                                           "a b and c\n")
        assert slicer.orca_log_conflicts(out) == [(f"Block #{i}", f"Block #{i + 1}") for i in range(1, 6)]
        assert slicer.orca_log_conflicts(out / "missing") == []

    def test_warnings_beside_entries_of_other_shapes_are_kept(self, out):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        (out / "result.json").write_text(json.dumps({"sliced_plates": ["x", {"warning_message": " Too thin "}]}))
        assert read_summary(out / "x.gcode.3mf", out)["warnings"] == ["Too thin"]

    @pytest.mark.parametrize("entry", ["Metadata/plate_1.gcode", "Metadata/slice_info.config"])
    def test_corrupt_entry_in_a_readable_zip_is_unreadable_output(self, out, entry):
        out.mkdir()
        others = [(name, "; total layer number: 5\n") for name in ("Metadata/plate_1.gcode", "Metadata/slice_info.config")
                  if name != entry]
        corrupt_entry(out / "x.gcode.3mf", entry, "G1 X1 Y1 E0.1\n" * 500, others)
        with pytest.raises(SliceError) as caught:
            read_summary(out / "x.gcode.3mf", out)
        assert (caught.value.error_code, caught.value.message) == ("slice.unreadable_output",
                                                                   "The sliced file the slicer wrote is damaged.")
        assert caught.value.details.startswith("x.gcode.3mf: ")

    def test_a_directory_entry_asking_for_an_unknown_zip_version_is_damage_worth_retrying(self, out):
        # zipfile raises NotImplementedError ("zip file version 23.5") for such an entry: it
        # was once "The slicer failed unexpectedly.", slice.unexpected, not worth retrying.
        from penguin_slice.errors import error_report
        out.mkdir()
        archive = out / "x.gcode.3mf"
        make_archive(archive)
        raw = bytearray(archive.read_bytes())
        directory = raw.index(b"PK\x01\x02")                 # the first central directory entry
        raw[directory + 6] = 235                             # its "version needed to extract": 23.5
        archive.write_bytes(bytes(raw))
        with pytest.raises(SliceError) as caught:
            read_summary(archive, out)
        report = error_report(caught.value)
        assert (report["code"], report["message"], report["retryable"]) == (
            "slice.unreadable_output", "The sliced file the slicer wrote is damaged.", True)
        assert "NotImplementedError" in report["detail"] and "23.5" in report["detail"]

    def test_archive_without_gcode_entry_names_contents(self, out):
        out.mkdir()
        make_archive(out / "p.gcode.3mf", gcode_header=False)
        with pytest.raises(SliceError) as caught:
            read_summary(out / "p.gcode.3mf", out)
        assert caught.value.message == "The sliced file the slicer wrote has no G-code in it."
        assert caught.value.details == "archive entries:\nMetadata/slice_info.config\n[Content_Types].xml"

    def test_gcode_header_is_read_without_decompressing_the_whole_entry(self, out):
        out.mkdir()
        archive = out / "big.gcode.3mf"
        filler = "G1 X1.0 Y1.0 E0.01\n" * 5000
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Metadata/plate_1.gcode", (FIXTURES / "plate_1_header.gcode").read_text() + filler)
            zf.writestr("Metadata/slice_info.config", (FIXTURES / "slice_info.config").read_text())
        real_read = zipfile.ZipFile.read

        def guarded_read(zf_self, name, *args, **kwargs):
            entry = name.filename if isinstance(name, zipfile.ZipInfo) else name
            assert entry != "Metadata/plate_1.gcode", "read_summary decompressed the whole G-code entry"
            return real_read(zf_self, name, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "read", guarded_read):
            summary = read_summary(archive, out)
        assert (summary["layer_count"], summary["print_time_s"]) == (50, 790.0)

    def test_corrupt_archive(self, out):
        out.mkdir()
        (out / "x.gcode.3mf").write_bytes(b"not a zip at all\x00\x01\x02")
        with pytest.raises(SliceError) as caught:
            read_summary(out / "x.gcode.3mf", out)
        assert caught.value.message == "The sliced file the slicer wrote is damaged."
        assert caught.value.details.startswith("x.gcode.3mf is not a zip archive")

    def test_missing_summary_fields_are_none(self, out):
        out.mkdir()
        make_archive(out / "p.gcode.3mf", slice_info=False)
        summary = read_summary(out / "p.gcode.3mf", out)
        assert (summary["print_time_s"], summary["filament_g"], summary["filament_m"]) == (None, None, None)
        assert summary["layer_count"] == 50

    def test_unparsable_numbers_and_no_layer_line_are_none(self, out):
        out.mkdir()
        with zipfile.ZipFile(out / "p.gcode.3mf", "w") as zf:
            zf.writestr("Metadata/plate_1.gcode", "; HEADER_BLOCK_START\n; HEADER_BLOCK_END\n")
            zf.writestr("Metadata/slice_info.config", '<metadata key="prediction" value="soon"/>'
                                                      '<filament id="1" used_m="lots"/>')
        summary = read_summary(out / "p.gcode.3mf", out)
        assert summary == {"print_time_s": None, "filament_g": None, "filament_m": None,
                           "layer_count": None, "warnings": []}


class TestVerifyArchive:
    def test_damage_past_the_header_is_found(self, out):
        out.mkdir()
        corrupt_entry(out / "x.gcode.3mf", "Metadata/plate_1.gcode", "G1 X1 Y1 E0.1\n" * 500)
        with pytest.raises(SliceError) as caught:
            slicer.verify_archive(out / "x.gcode.3mf")
        assert caught.value.error_code == "slice.unreadable_output"

    def test_bad_crc_is_found(self, out, monkeypatch):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: "Metadata/plate_1.gcode")
        with pytest.raises(SliceError) as caught:
            slicer.verify_archive(out / "x.gcode.3mf")
        assert caught.value.details == "x.gcode.3mf: entry Metadata/plate_1.gcode fails its checksum"

    def test_good_archive_passes(self, out):
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        slicer.verify_archive(out / "x.gcode.3mf")


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "plate.3mf"
    path.write_bytes(b"PK")
    return path


def supports_profiles(tmp_path, value):
    process = json.loads((slicer.PROFILE_DIR / "process.json").read_text())
    process["enable_support"] = value
    (tmp_path / "process.json").write_text(json.dumps(process))
    return slicer.SliceProfiles(slicer.PROFILE_DIR / "printer.json", slicer.PROFILE_DIR / "filament.json",
                                tmp_path / "process.json")


EMPTY = ("Object can't be printed for empty layer between 9.9 and 11.34.\nObject: Gap #1\n"
         "Maybe parts of the object at these height are too thin, or the object has faulty mesh")


class TestPlateSlice:
    def test_plate_command_disables_arrange_and_orient(self, tmp_path, out, model, placeholder_orca):
        profiles = slicer.SliceProfiles(tmp_path / "p.json", tmp_path / "f.json", tmp_path / "q.json")
        cmd = slicer.build_plate_command(model, profiles, out)
        assert cmd == [
            str(placeholder_orca),
            "--debug", "3", "--logfile", str(out / "orca.log"),
            "--datadir", str(out / "datadir"),
            "--load-settings", f"{(tmp_path / 'p.json').resolve()};{(tmp_path / 'q.json').resolve()}",
            "--load-filaments", str((tmp_path / "f.json").resolve()),
            "--arrange", "0",
            "--orient", "0",
            "--slice", "0",
            "--pipe", str(out / "orca-progress.fifo"),
            "--export-3mf", "plate.gcode.3mf",
            "--outputdir", str(out),
            str(model.resolve()),
        ]

    def test_default_profiles_are_the_three_files(self):
        assert slicer.DEFAULT_PROFILES == slicer.SliceProfiles(
            slicer.PROFILE_DIR / "printer.json", slicer.PROFILE_DIR / "filament.json",
            slicer.PROFILE_DIR / "process.json")

    def test_slice_plate_uses_plate_timeout_and_reads_summary(self, out, model, executable_orca):
        fake = fake_run_factory()
        with patched(fake):
            result = slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert fake.calls[0][1]["timeout_s"] == limits.PLATE_SLICE_TIMEOUT_S == 240
        assert fake.calls[0][1]["env"]["LC_ALL"] == "C"
        assert result.output_path == out / "plate.gcode.3mf"
        assert result.layer_count == 50

    @pytest.mark.parametrize("reason", ["cancel", "replaced", "shutdown", "requested"])
    def test_a_stop_set_before_orca_starts_never_starts_it(self, out, model, executable_orca, reason):
        fake, stop = fake_run_factory(), slicer.Stop()
        stop.set(reason)
        with patched(fake), pytest.raises(SliceCancelled) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out, stop=stop)
        assert fake.calls == []
        assert caught.value.details == f"stopped by the slice service ({reason}) before Orca was started"
        assert not (out / slicer.PLATE_ARCHIVE).exists()

    @pytest.mark.parametrize("code, error_code, message", [
        (-101, "slice.orca_too_close", TOO_CLOSE),
        (-52, "slice.crosses_edge", "A part crosses the edge of the plate."),
        (-100, "slice.orca_failed", "The slicer could not slice this plate."),
        (-50, "slice.nothing_on_plate", "No part is fully on the plate."),
        (-6, "slice.orca_failed", "The slicer could not slice this plate."),
    ])
    def test_orca_codes_map_to_messages(self, out, model, executable_orca, code, error_code, message):
        with patched(fake_result_run(returncode=(code + 256) % 256, return_code=code)):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert (caught.value.error_code, caught.value.message) == (error_code, message)
        assert caught.value.code == code
        assert caught.value.details.splitlines()[0] == f"exit code {(code + 256) % 256}"
        assert "orca says no" in caught.value.details
        assert caught.value.reason == "x"

    def test_code_table_is_the_four_known_codes(self):
        assert slicer.ORCA_RETURN_CODES == {
            -101: ("slice.orca_too_close", TOO_CLOSE),
            -52: ("slice.crosses_edge", "A part crosses the edge of the plate."),
            -100: ("slice.orca_failed", "The slicer could not slice this plate."),
            -50: ("slice.nothing_on_plate", "No part is fully on the plate."),
        }

    def test_orca_reasons_are_kept_in_the_details(self, out, model, executable_orca):
        fake = fake_result_run(returncode=156, return_code=-100, warning="Too thin here")
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.details.splitlines()[:4] == ["exit code 156", "orca error_string: x",
                                                         "orca warning_message: Too thin here", "orca says no"]
        assert caught.value.reason == "x\nToo thin here"

    @pytest.mark.parametrize("enable, error_code", [("0", "slice.empty_layers"), ("1", "slice.empty_layers_with_supports")])
    def test_empty_layers_name_the_instance_and_the_height(self, tmp_path, out, model, executable_orca, enable,
                                                       error_code):
        with patched(fake_result_run(156, -100, error_string="Failed slicing the model.", warning=EMPTY)):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, supports_profiles(tmp_path, enable), out)
        assert caught.value.error_code == error_code
        assert caught.value.message == ("Gap #1 has nothing to print between 9.9 and 11.34 mm high, so the layers "
                                        "above would start in mid-air.")
        assert caught.value.where == {"instance": "Gap #1", "height_mm": 9.9}

    def test_empty_layers_without_an_object_name(self, out, model, executable_orca):
        warning = "Object can't be printed for empty layer between 1.5 and 2.0."
        with patched(fake_result_run(156, -100, warning=warning)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.message.startswith("A part has nothing to print between 1.5 and 2.0 mm high")
        assert caught.value.where == {"height_mm": 1.5}

    def test_unreadable_process_profile_counts_as_supports_unknown(self, tmp_path, out, model, executable_orca):
        (tmp_path / "process.json").write_text("{broken")
        profiles = slicer.SliceProfiles(slicer.PROFILE_DIR / "printer.json", slicer.PROFILE_DIR / "filament.json",
                                        tmp_path / "process.json")
        with patched(fake_result_run(156, -100, warning=EMPTY)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, profiles, out)
        assert caught.value.error_code == "slice.empty_layers"
        assert slicer.process_supports_on(tmp_path / "process.json") is None

    @pytest.mark.parametrize("content", ['{"return_code": -100, "error_string": 7}', '{"return_code": -100}',
                                         '{"return_code": -100, "error_string": "  "}'])
    def test_details_without_a_usable_error_string(self, out, model, executable_orca, content):
        fake = fake_run_factory(156, write_archive=False, stdout="orca says no", result=content)
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.details == "exit code 156\norca says no"

    def test_bad_alloc_is_out_of_memory_whatever_the_code(self, out, model, executable_orca):
        with patched(fake_result_run(156, -100, stdout="std::bad_alloc\nrun found error, return -100, exit...")):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert (caught.value.error_code, caught.value.message) == (
            "slice.out_of_memory", "This plate is too large to slice: the slicer ran out of memory.")

    @pytest.mark.parametrize("returncode, error_code", [
        (-signal.SIGKILL, "slice.orca_killed"), (-signal.SIGSEGV, "slice.orca_crashed"),
        (-signal.SIGABRT, "slice.orca_crashed"), (-signal.SIGBUS, "slice.orca_crashed"),
        (-signal.SIGFPE, "slice.orca_crashed"), (-signal.SIGILL, "slice.orca_crashed"),
        (-signal.SIGTERM, "slice.orca_killed"), (-signal.SIGINT, "slice.orca_killed"), (-99, "slice.orca_killed"),
    ])
    def test_a_signal_we_did_not_send_is_read_truthfully(self, out, model, executable_orca, returncode, error_code):
        stdout = "\n".join(f"line {i}" for i in range(30))
        with patched(fake_run_factory(returncode=returncode, write_archive=False, stdout=stdout)):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == error_code
        details = caught.value.details.splitlines()
        assert details[0].startswith(f"ended by signal {-returncode} (")
        assert details[0].endswith("not sent by the slice service; the kernel's oom_kill count could not be read")
        assert details[1:] == [f"line {i}" for i in range(11, 30)]

    @pytest.mark.parametrize("returncode", [126, 127])
    def test_an_orca_the_shell_or_loader_could_not_start(self, out, model, executable_orca, returncode):
        # Once "Try another orientation or other print settings": the plate's fault.
        with patched(fake_run_factory(returncode, write_archive=False, write_result_json=False,
                                      stdout="orca-slicer: error while loading shared libraries: libx.so")):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.orca_unstartable"
        assert caught.value.details.startswith(f"exit code {returncode}: Orca did not start")

    def test_exit_127_with_orcas_own_result_is_orcas_failure(self, out, model, executable_orca):
        with patched(fake_result_run(127, -100)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.orca_failed"

    def test_a_sigkill_with_the_kernels_count_risen_is_out_of_memory(self, out, model, executable_orca):
        with patched(lambda cmd, **kwargs: OrcaExit(-9, "slicing", oom_kills=2)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.out_of_memory"

    def test_abort_after_bad_alloc_is_out_of_memory(self, out, model, executable_orca):
        fake = fake_run_factory(-signal.SIGABRT, write_archive=False, stdout="std::bad_alloc\nterminate called")
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.out_of_memory"

    def test_kernel_oom_kill_count_reaches_the_detail(self, out, model, executable_orca):
        def fake(cmd, **kwargs):
            return OrcaExit(-9, "slicing", oom_kills=1)
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert "the kernel's oom_kill count rose by 1" in caught.value.details

    def test_wrapper_that_does_not_exec_reports_the_signal_as_status(self, out, model, executable_orca):
        with patched(fake_run_factory(137, write_archive=False, write_result_json=False, stdout="Killed")):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.orca_killed"          # the kernel's count did not say memory
        assert caught.value.details.startswith("ended by signal 9 (SIGKILL)")

    def test_exit_155_with_orcas_own_line_is_orcas_code(self, out, model, executable_orca):
        fake = fake_run_factory(155, write_archive=False, write_result_json=False,
                                stdout="run found error, return -101, exit...")
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.code == -101
        assert caught.value.error_code == "slice.orca_too_close"

    def test_sample_part_stopped_by_a_signal(self, out, executable_orca):
        with patched(fake_run_factory(returncode=-11, write_archive=False)), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.error_code == "slice.orca_crashed"

    def test_return_code_from_result_json_or_exit_status(self, out):
        out.mkdir()
        assert slicer.orca_return_code(out, 155) == -101          # no result.json: the exit byte
        assert slicer.orca_return_code(out, 1) is None
        (out / "result.json").write_text(json.dumps({"return_code": -52}))
        assert slicer.orca_return_code(out, 155) == -52
        for unusable in ('{"return_code": 0}', '{"return_code": true}', '{"return_code": "-52"}', "[1]",
                         "not json"):
            (out / "result.json").write_text(unusable)
            assert slicer.orca_return_code(out, 204) == -52, unusable

    def test_unknown_orca_code_keeps_orcas_words(self, out, model, executable_orca):
        fake = fake_result_run(179, -77, error_string="Something Orca has never said before.")
        with patched(fake), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert (caught.value.error_code, caught.value.code) == ("slice.orca_failed", -77)
        assert "orca error_string: Something Orca has never said before." in caught.value.details


class TestProgressLines:
    def test_orca_messages_become_stages_and_fractions(self):
        seen = []
        line = json.dumps({"message": "Generating walls", "plate_count": 1, "plate_index": 1,
                           "plate_percent": 15, "total_percent": 16})
        slicer._progress_line(line, lambda *args: seen.append(args))
        assert seen == [("generating_walls", 0.16, "Generating walls")]

    @pytest.mark.parametrize("line", ["not json", "[1]", '{"total_percent": 5}', '{"message": 3}'])
    def test_lines_that_are_not_messages_are_ignored(self, line):
        seen = []
        slicer._progress_line(line, lambda *args: seen.append(args))
        assert seen == []

    @pytest.mark.parametrize("percent", [None, -1, 101, True, "50"])
    def test_a_percent_out_of_range_gives_no_fraction(self, percent):
        seen = []
        slicer._progress_line(json.dumps({"message": "Odd new stage", "total_percent": percent}),
                              lambda *args: seen.append(args))
        assert seen == [(None, None, "Odd new stage")]


class TestPartInfo:
    def test_bounds_of_binary_stl(self):
        tri = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 3, 0, 0, 0, 5, 0, 0)
        tri2 = struct.pack("<12fH", 0, 0, 1, -1, 0, 2, 3, 0, 0, 0, 5, 0, 0)
        data = b"\0" * 80 + struct.pack("<I", 2) + tri + tri2
        assert stl_bounds(data) == ((-1.0, 0.0, 0.0), (3.0, 5.0, 2.0), 2)

    def test_bounds_of_ascii_stl(self):
        text = ("solid t\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 0\n   vertex 10 0 0\n"
                "   vertex 0 20 5\n  endloop\n endfacet\nendsolid t\n")
        assert stl_bounds(text.encode()) == ((0.0, 0.0, 0.0), (10.0, 20.0, 5.0), 1)

    def test_bounds_of_stl_without_triangles_refused(self):
        with pytest.raises(ValueError, match="STL has no triangles"):
            stl_bounds(b"solid empty\nendsolid empty\n")

    def test_binary_length_rule(self):
        assert slicer._binary_triangle_count(b"\0" * 83) is None
        assert slicer._binary_triangle_count(b"\0" * 80 + struct.pack("<I", 1) + b"\0" * 49) is None
        assert slicer._binary_triangle_count(b"solid" + b"\0" * 75 + struct.pack("<I", 1) + b"\0" * 50) == 1

    def test_part_info_reads_sample_part_and_profiles(self):
        info = part_info()
        assert info["part"] == {"name": "sample_part", "file": "sample_part.stl",
                                "size_mm": {"x": 40.0, "y": 30.0, "z": 12.0}, "triangles": 20}
        assert info["printer"] == {"name": "Bambu Lab H2S 0.6 nozzle", "bed_mm": {"x": 340.0, "y": 320.0},
                                   "height_mm": 340.0}
        assert info["filament"] == {"name": "Generic PETG @BBL H2S"}
        assert info["process"] == {"name": "0.24mm Balanced Quality @BBL H2S 0.6 nozzle", "layer_height_mm": 0.24}

    def test_bed_size_without_printable_area(self):
        assert slicer._bed_size({}) == {"x": None, "y": None}
        assert slicer._bed_size({"printable_area": ["10x5", "110X5", "110x45", "10x45"]}) == {"x": 100.0, "y": 40.0}


class TestProfileFiles:
    REQUIRED = {
        "printer.json": ("name", "printable_area", "printable_height"),
        "filament.json": ("name", "filament_density", "compatible_printers"),
        "process.json": ("name", "layer_height", "compatible_printers"),
    }

    def test_profiles_are_flat_and_carry_required_keys(self):
        for fname, keys in self.REQUIRED.items():
            data = json.loads((slicer.PROFILE_DIR / fname).read_text())
            assert (data.get("inherits"), data.get("from")) == ("", "system"), fname
            for key in keys:
                assert key in data, f"{fname} lacks {key}"

    def test_process_and_filament_are_compatible_with_the_printer(self):
        printer = slicer.default_printer_profile()["name"]
        for fname in ("filament.json", "process.json"):
            assert printer in json.loads((slicer.PROFILE_DIR / fname).read_text())["compatible_printers"], fname


class TestNozzleVariant:
    """The checked-in profiles must select the High Flow nozzle and the textured plate."""
    VARIANT = "Direct Drive High Flow"

    @pytest.fixture(autouse=True)
    def profiles(self):
        self.machine = json.loads((slicer.PROFILE_DIR / "printer.json").read_text())
        self.filament = json.loads((slicer.PROFILE_DIR / "filament.json").read_text())
        self.process = json.loads((slicer.PROFILE_DIR / "process.json").read_text())

    def test_machine_selects_high_flow(self):
        assert self.machine["nozzle_volume_type"] == ["High Flow"]
        assert self.machine["extruder_type"] == ["Direct Drive"]
        assert self.machine["nozzle_diameter"] == ["0.6"]
        assert self.machine["nozzle_type"] == ["hardened_steel", "hardened_steel"]

    def test_every_profile_offers_the_variant_at_the_same_index(self):
        indexes = {self.machine["printer_extruder_variant"].index(self.VARIANT),
                   self.filament["filament_extruder_variant"].index(self.VARIANT),
                   self.process["print_extruder_variant"].index(self.VARIANT)}
        assert indexes == {1}

    def test_dual_valued_keys_are_not_collapsed_to_one_element(self):
        assert self.machine["nozzle_volume"] == ["145", "148"]
        assert self.machine["nozzle_flush_dataset"] == ["1", "2"]
        assert len(self.filament["filament_extruder_variant"]) == 2

    def test_petg_values_are_the_profile_values_not_invented_ones(self):
        assert self.filament["filament_max_volumetric_speed"] == ["12", "12"]
        assert self.filament["nozzle_temperature"] == ["255", "255"]
        assert self.filament["filament_type"] == ["PETG"]

    def test_textured_plate_is_selected_by_name_and_number(self):
        assert self.machine["curr_bed_type"] == "Textured PEI Plate"
        assert self.machine["default_bed_type"] == "4"
        assert self.filament["textured_plate_temp"] == ["70"]
