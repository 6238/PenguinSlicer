"""The Makefile's fast suite: a failing order can be repeated from its log, so the tools' tests
print the seed pytest-randomly chose."""
import shlex
import subprocess
from pathlib import Path

WIZARD = Path(__file__).resolve().parents[2]


def test_the_tools_tests_print_their_random_seed(tmp_path):
    shown = subprocess.run(["make", "--no-print-directory", "-s", "-n", "-C", str(WIZARD), "test-tools"],
                           capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    command = shlex.split(shown)
    assert str(WIZARD / "tests" / "python") in command, shown
    (tmp_path / "test_one.py").write_text("def test_one():\n    pass\n")
    command = [str(tmp_path) if word == str(WIZARD / "tests" / "python") else word for word in command]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, cwd=WIZARD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Using --randomly-seed=" in result.stdout, result.stdout
