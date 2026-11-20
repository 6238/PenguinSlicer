"""The command line, `python -m penguin_slice slice <plate-job.json> --out <dir>`, run in
process against the contract's example plate job and a fake Orca."""
import io
import json
import runpy
import sys

import pytest

from helpers import CONTRACTS, install_fake_orca
from penguin_slice.__main__ import main

EXAMPLE = CONTRACTS / "examples" / "plate-job.json"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_slices_the_example_and_prints_the_summary(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    code, out, err = run(["slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    assert (code, err) == (0, "")
    summary = json.loads(out)
    assert summary["file"] == "Bracket_plus1-20261009-1432.gcode.3mf"
    assert summary["copies"] == 3
    assert (tmp_path / "out" / summary["file"]).is_file()


def test_failure_prints_the_error_report_and_exits_one(tmp_path):
    # The autouse placeholder Orca cannot start.
    code, out, err = run(["slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    assert (code, out) == (1, "")
    report = json.loads(err)
    assert report["code"] == "slice.orca_unstartable"
    assert report["message"] == "The slicer could not be started."


def test_refused_plate_job_exits_one(tmp_path):
    path = tmp_path / "plate-job.json"
    path.write_text("[]")
    code, out, err = run(["slice", str(path), "--out", str(tmp_path / "out")])
    assert (code, out, json.loads(err)["code"]) == (1, "", "slice.bad_plate_job")


@pytest.mark.parametrize("argv", [[], ["slice"], ["slice", "x.json"], ["cut", "x.json", "--out", "o"]])
def test_usage_errors_exit_two(argv, capsys):
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 2
    assert "usage: python -m penguin_slice" in capsys.readouterr().err


def test_module_entry_point(tmp_path, monkeypatch, capsys):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    monkeypatch.setattr(sys, "argv", ["penguin_slice", "slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    monkeypatch.delitem(sys.modules, "penguin_slice.__main__", raising=False)   # run it fresh, as -m does
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("penguin_slice", run_name="__main__", alter_sys=False)
    assert caught.value.code == 0
    assert json.loads(capsys.readouterr().out)["copies"] == 3
