"""slicer.py: the command lines, Orca's isolation, its failures and the summary. Orca is
never run: subprocess.run is replaced, or the binary is a placeholder."""
import json
import os
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from helpers import FIXTURES, corrupt_entry, make_archive
from penguin_slice import limits
from penguin_slice import slicer
from penguin_slice.slicer import SliceError, build_command, part_info, read_summary, slice_stl, stl_bounds


def fake_run_factory(returncode=0, write_archive=True, write_result_json=True, stdout="log line\n",
                     raise_timeout=False, timeout_output=None):
    """A stand-in for subprocess.run that behaves like Orca's exit."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if raise_timeout:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"), output=timeout_output)
        outdir = Path(cmd[cmd.index("--outputdir") + 1])
        name = cmd[cmd.index("--export-3mf") + 1]
        if write_archive:
            make_archive(outdir / name)
        if write_result_json:
            shutil.copy(FIXTURES / "result.json", outdir / "result.json")
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    fake_run.calls = calls
    return fake_run


def fake_result_run(returncode, return_code=None):
    """A stand-in that writes no archive, and a result.json carrying `return_code` unless None."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if return_code is not None:
            outdir = Path(cmd[cmd.index("--outputdir") + 1])
            (outdir / "result.json").write_text(json.dumps({"return_code": return_code, "error_string": "x"}))
        return subprocess.CompletedProcess(cmd, returncode, stdout="orca says no\n", stderr="")

    fake_run.calls = calls
    return fake_run


@pytest.fixture
def out(tmp_path):
    # .resolve(): the slice functions resolve their arguments, and on macOS /tmp is a
    # symlink, so an unresolved path would not compare equal.
    return tmp_path.resolve() / "out"


def patched(fake):
    return mock.patch.object(slicer.subprocess, "run", fake)


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
        # The original module refused to import without Orca; the port looks only when slicing.
        monkeypatch.setenv(slicer.ORCA_ENV, str(tmp_path / "no-such-orca"))
        assert slicer.build_command(slicer.SAMPLE_STL, tmp_path)[0] == str(tmp_path / "no-such-orca")


class TestSampleCommand:
    def test_command_uses_binary_default_profiles_and_flags(self, out, placeholder_orca):
        cmd = build_command(slicer.SAMPLE_STL, out)
        assert cmd == [
            str(placeholder_orca),
            "--datadir", str(out / "datadir"),
            "--load-settings", f"{slicer.PROFILE_DIR / 'printer.json'};{slicer.PROFILE_DIR / 'process.json'}",
            "--load-filaments", str(slicer.PROFILE_DIR / "filament.json"),
            "--arrange", "1",
            "--slice", "0",
            "--export-3mf", "sample_part.gcode.3mf",
            "--outputdir", str(out),
            str(slicer.SAMPLE_STL),
        ]

    def test_relative_paths_are_resolved_to_absolute(self):
        # Orca runs with cwd=output_dir, so a relative argument would be read against the
        # wrong directory. No chdir: the expectation is computed from whatever cwd is.
        cmd = build_command(Path("parts/sample_part.stl"), Path("out"))
        assert cmd[-1] == str(Path("parts/sample_part.stl").resolve())
        assert cmd[cmd.index("--outputdir") + 1] == str(Path("out").resolve())
        assert cmd[cmd.index("--datadir") + 1] == str(Path("out").resolve() / "datadir")
        for token in cmd:
            for piece in token.split(";"):
                if "/" in piece:
                    assert Path(piece).is_absolute(), piece
        # --export-3mf is a bare name on purpose: Orca writes it into --outputdir.
        assert cmd[cmd.index("--export-3mf") + 1] == "sample_part.gcode.3mf"


class TestSliceStl:
    def test_slice_creates_output_dir_and_isolated_environment(self, out, monkeypatch):
        monkeypatch.setenv("SLICE_SECRET_MARKER", "x")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        fake = fake_run_factory()
        with patched(fake):
            result = slice_stl(slicer.SAMPLE_STL, out)
        assert out.is_dir()
        cmd, kwargs = fake.calls[0]
        env = kwargs["env"]
        # The caller's environment may hold secrets; Orca sees an allowlist.
        assert "SLICE_SECRET_MARKER" not in env
        assert slicer.ORCA_ENV not in env
        assert set(env) <= set(slicer.ENV_ALLOWLIST) | {"XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "LC_ALL"}
        assert env["PATH"] == "/usr/bin:/bin"
        assert env["XDG_CONFIG_HOME"] == str(out / "xdg-config")
        assert env["XDG_RUNTIME_DIR"] == str(out / "xdg-runtime")
        assert env["LC_ALL"] == "C"
        assert (out / "xdg-runtime").stat().st_mode & 0o777 == 0o700
        assert kwargs["cwd"] == str(out)
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["timeout"] == slicer.DEFAULT_TIMEOUT_S == 120
        assert result.output_path == out / "sample_part.gcode.3mf"

    def test_summary_from_archive_and_result_json(self, out):
        with patched(fake_run_factory()):
            result = slice_stl(slicer.SAMPLE_STL, out)
        assert result.summary() == {"print_time_s": 790.0, "filament_m": 1.09, "filament_g": 3.31,
                                    "layer_count": 50, "warnings": []}

    def test_relative_arguments_reach_orca_as_absolute_paths(self, out):
        fake = fake_run_factory()
        relative_out = os.path.relpath(out)
        with patched(fake):
            result = slice_stl(os.path.relpath(slicer.SAMPLE_STL), relative_out)
        cmd, kwargs = fake.calls[0]
        assert Path(cmd[-1]) == slicer.SAMPLE_STL
        assert Path(kwargs["cwd"]).is_absolute()
        assert result.output_path == out / "sample_part.gcode.3mf"

    def test_nonzero_exit_raises_with_code_and_last_lines(self, out):
        stdout = "".join(f"line {i}\n" for i in range(30))
        with patched(fake_run_factory(returncode=255, write_archive=False, stdout=stdout)):
            with pytest.raises(SliceError) as caught:
                slice_stl(slicer.SAMPLE_STL, out)
        details = caught.value.details.splitlines()
        # The exit code takes the first of the twenty lines, so the tail of the output
        # starts one line later than the output alone would.
        assert details[0] == "exit code 255"
        assert details[1:] == [f"line {i}" for i in range(11, 30)]
        assert caught.value.message == "The slicer could not process this part."
        assert caught.value.code == 255

    def test_unstartable_slicer(self, out):
        def boom(cmd, **kwargs):
            raise OSError(8, "Exec format error", cmd[0])

        with patched(boom), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.message == "The slicer could not be started."
        assert "Exec format error" in caught.value.details
        assert caught.value.code is None

    def test_placeholder_binary_is_unstartable_without_mocking(self, out):
        # The suite's safety net: the real subprocess.run on the non-executable placeholder.
        with pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.message == "The slicer could not be started."
        assert "Permission denied" in caught.value.details

    @pytest.mark.parametrize("captured, expected", [
        (None, ""),
        ("text line 1\ntext line 2\n", "text line 1\ntext line 2"),
        (b"bytes line\n\xff\n", "bytes line\n�"),
    ])
    def test_timeout_keeps_what_orca_printed(self, out, captured, expected):
        fake = fake_run_factory(raise_timeout=True, timeout_output=captured)
        with patched(fake), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out, timeout_s=7)
        assert caught.value.message == "The slicer took too long on this part."
        assert caught.value.code == "timeout"
        assert caught.value.details == expected
        assert fake.calls[0][1]["timeout"] == 7

    def test_missing_archive_after_exit_zero(self, out):
        stdout = "".join(f"line {i}\n" for i in range(25))
        with patched(fake_run_factory(write_archive=False, stdout=stdout)), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.message == "The slicer produced no output file."
        assert caught.value.details.splitlines() == [f"line {i}" for i in range(5, 25)]


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
                                         b'{"sliced_plates": [{"warning_message": ""}]}\xff'])
    def test_result_json_of_any_shape_gives_no_warnings_and_keeps_the_slice(self, out, content):
        # A good slice is never thrown away over Orca's side file (contracts/sliced-file.md).
        out.mkdir()
        make_archive(out / "x.gcode.3mf")
        if isinstance(content, bytes):
            (out / "result.json").write_bytes(content)
        else:
            (out / "result.json").write_text(content)
        summary = read_summary(out / "x.gcode.3mf", out)
        assert summary["warnings"] == []
        assert summary["layer_count"] == 50

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
                                                                   "The slicer output could not be read.")
        assert caught.value.details.startswith("x.gcode.3mf: ")

    def test_archive_without_gcode_entry_names_contents(self, out):
        out.mkdir()
        make_archive(out / "p.gcode.3mf", gcode_header=False)
        with pytest.raises(SliceError) as caught:
            read_summary(out / "p.gcode.3mf", out)
        assert caught.value.message == "The slicer output is missing its G-code."
        assert caught.value.details == "archive entries:\nMetadata/slice_info.config\n[Content_Types].xml"

    def test_gcode_header_is_read_without_decompressing_the_whole_entry(self, out):
        out.mkdir()
        archive = out / "big.gcode.3mf"
        filler = "G1 X1.0 Y1.0 E0.01\n" * 5000          # far past GCODE_HEAD_BYTES
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
        assert caught.value.message == "The slicer output could not be read."
        assert caught.value.details == "x.gcode.3mf is not a zip archive"

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


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "plate.3mf"
    path.write_bytes(b"PK")
    return path


class TestPlateSlice:
    def test_plate_command_disables_arrange_and_orient(self, tmp_path, out, model, placeholder_orca):
        profiles = slicer.SliceProfiles(tmp_path / "p.json", tmp_path / "f.json", tmp_path / "q.json")
        cmd = slicer.build_plate_command(model, profiles, out)
        assert cmd == [
            str(placeholder_orca),
            "--datadir", str(out / "datadir"),
            "--load-settings", f"{(tmp_path / 'p.json').resolve()};{(tmp_path / 'q.json').resolve()}",
            "--load-filaments", str((tmp_path / "f.json").resolve()),
            "--arrange", "0",
            "--orient", "0",
            "--slice", "0",
            "--export-3mf", "plate.gcode.3mf",
            "--outputdir", str(out),
            str(model.resolve()),
        ]

    def test_default_profiles_are_the_three_files(self):
        assert slicer.DEFAULT_PROFILES == slicer.SliceProfiles(
            slicer.PROFILE_DIR / "printer.json", slicer.PROFILE_DIR / "filament.json",
            slicer.PROFILE_DIR / "process.json")

    def test_slice_plate_uses_plate_timeout_and_reads_summary(self, out, model):
        fake = fake_run_factory()
        with patched(fake):
            result = slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert fake.calls[0][1]["timeout"] == limits.PLATE_SLICE_TIMEOUT_S == 240
        assert fake.calls[0][1]["env"]["LC_ALL"] == "C"
        assert fake.calls[0][1]["cwd"] == str(out)
        assert result.output_path == out / "plate.gcode.3mf"
        assert result.layer_count == 50

    @pytest.mark.parametrize("code, message", [
        (-101, "Parts are too close together; spread them out."),
        (-52, "A part crosses the edge of the plate."),
        (-100, "A part has no flat face on the plate; choose another Lay flat."),
        (-50, "No part is fully on the plate."),
        (-6, "The slicer could not process this part."),
    ])
    def test_orca_codes_map_to_messages(self, out, model, code, message):
        with patched(fake_result_run(returncode=(code + 256) % 256, return_code=code)):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.message == message
        assert caught.value.code == code
        assert caught.value.details.splitlines()[0] == f"exit code {(code + 256) % 256}"
        assert "orca says no" in caught.value.details

    def test_code_table_is_the_four_known_codes(self):
        assert slicer.ORCA_RETURN_CODES == {
            -101: ("slice.orca_too_close", "Parts are too close together; spread them out."),
            -52: ("slice.crosses_edge", "A part crosses the edge of the plate."),
            -100: ("slice.empty_layers", "A part has no flat face on the plate; choose another Lay flat."),
            -50: ("slice.nothing_on_plate", "No part is fully on the plate."),
        }

    def test_orca_error_string_is_kept_in_the_details(self, out, model):
        with patched(fake_result_run(returncode=156, return_code=-100)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.details.splitlines()[:3] == ["exit code 156", "orca error_string: x", "orca says no"]

    @pytest.mark.parametrize("content", ['{"return_code": -100, "error_string": 7}', '{"return_code": -100}',
                                         '{"return_code": -100, "error_string": "  "}'])
    def test_details_without_a_usable_error_string(self, out, model, content):
        def fake_run(cmd, **kwargs):
            (Path(cmd[cmd.index("--outputdir") + 1]) / "result.json").write_text(content)
            return subprocess.CompletedProcess(cmd, 156, stdout="orca says no\n", stderr="")

        with patched(fake_run), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.details == "exit code 156\norca says no"

    @pytest.mark.parametrize("returncode, name", [(-9, "SIGKILL"), (-15, "SIGTERM"), (-99, "unknown signal")])
    def test_orca_stopped_by_a_signal_is_not_a_fault_of_the_part(self, out, model, returncode, name):
        stdout = "".join(f"line {i}\n" for i in range(30))
        with patched(fake_run_factory(returncode=returncode, write_archive=False, stdout=stdout)):
            with pytest.raises(SliceError) as caught:
                slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert (caught.value.error_code, caught.value.message) == (
            "slice.orca_killed", "The print server stopped the slicer before it finished.")
        assert caught.value.code is None
        details = caught.value.details.splitlines()
        assert details[0] == f"killed by signal {-returncode} ({name})"
        assert details[1:] == [f"line {i}" for i in range(11, 30)]

    def test_sample_part_stopped_by_a_signal(self, out):
        with patched(fake_run_factory(returncode=-9, write_archive=False)), pytest.raises(SliceError) as caught:
            slice_stl(slicer.SAMPLE_STL, out)
        assert caught.value.error_code == "slice.orca_killed"

    def test_orca_output_is_decoded_as_utf8_with_replacement(self, out, model):
        fake = fake_run_factory()
        with patched(fake):
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        kwargs = fake.calls[0][1]
        assert (kwargs["text"], kwargs["encoding"], kwargs["errors"]) == (True, "utf-8", "replace")

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

    def test_exit_status_code_when_orca_writes_no_result_json(self, out, model):
        with patched(fake_result_run(returncode=155)), pytest.raises(SliceError) as caught:
            slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out)
        assert caught.value.code == -101
        assert caught.value.message == "Parts are too close together; spread them out."


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
    """The checked-in profiles must select the High Flow nozzle and the textured plate.

    Orca resolves every variant-aware value by matching "<extruder_type> <nozzle_volume_type>"
    against each profile's *_extruder_variant array. With no nozzle_volume_type the command
    line falls back to Standard, which is index 0, silently.
    """
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
        # Collapsing would hide the choice and hard-code index 0.
        assert self.machine["nozzle_volume"] == ["145", "148"]
        assert self.machine["nozzle_flush_dataset"] == ["1", "2"]
        assert len(self.filament["filament_extruder_variant"]) == 2

    def test_petg_values_are_the_profile_values_not_invented_ones(self):
        assert self.filament["filament_max_volumetric_speed"] == ["12", "12"]
        assert self.filament["nozzle_temperature"] == ["255", "255"]
        assert self.filament["nozzle_temperature_initial_layer"] == ["255", "255"]
        assert self.filament["filament_flow_ratio"] == ["0.95", "0.95"]
        assert self.filament["filament_type"] == ["PETG"]

    def test_textured_plate_is_selected_by_name_and_number(self):
        assert self.machine["curr_bed_type"] == "Textured PEI Plate"
        # Preset::get_default_bed_type runs atoi() on this, so a name would parse as 0 and
        # fall back to the smooth High Temp Plate.
        assert self.machine["default_bed_type"] == "4"
        assert self.filament["textured_plate_temp"] == ["70"]
        assert self.filament["textured_plate_temp_initial_layer"] == ["70"]
