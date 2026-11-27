"""The check that Node is 24 or later, which `make install` and `make test` run first."""
import sys

import pytest

from scripts import check_node


@pytest.mark.parametrize("text", ["v24.0.0", "v24.19.0\n", "v25.1.3", "v100.0.0"])
def test_node_24_or_later_passes(text):
    assert check_node.check(text) is None


@pytest.mark.parametrize("text, shown", [("v22.3.0", "22.3.0"), ("v23.11.1\n", "23.11.1"),
                                         ("v18.20.4", "18.20.4"), ("v2.40.0", "2.40.0")])
def test_older_node_is_refused_naming_its_version(text, shown):
    message = check_node.check(text)
    assert message == f"Node {shown} is older than 24: the wizard's tests need Node 24 or later."


@pytest.mark.parametrize("text", ["", "node", "24", "v24", "vX.1.2"])
def test_an_unreadable_version_is_refused_quoting_it(text):
    message = check_node.check(text)
    assert message == f"Could not read Node's version from {text.strip()!r}: the wizard's tests need Node 24 or later."


def test_main_passes_with_this_machines_node(capsys):
    assert check_node.main(["check_node.py", "node"]) == 0


def test_main_names_a_missing_node():
    assert check_node.main(["check_node.py", "/nonexistent/node-24"]) == 1


def test_main_reports_an_old_node(tmp_path, capsys):
    fake = tmp_path / "node"
    fake.write_text(f"#!{sys.executable}\nprint('v20.1.0')\n")
    fake.chmod(0o755)
    assert check_node.main(["check_node.py", str(fake)]) == 1
    assert "Node 20.1.0 is older than 24" in capsys.readouterr().err


def test_main_reports_a_missing_node_by_name(capsys):
    check_node.main(["check_node.py", "/nonexistent/node-24"])
    assert capsys.readouterr().err.strip() == (
        "Node was not found as '/nonexistent/node-24': the wizard's tests need Node 24 or later.")
