"""The slice service stands alone: its package and scripts import only the standard library,
numpy, shapely and the package itself; nothing of a web framework, Onshape, a team
configuration or another component."""
import ast
import sys

import pytest

from helpers import SLICE_ROOT

PACKAGE = SLICE_ROOT / "src" / "penguin_slice"
ALLOWED = set(sys.stdlib_module_names) | {"numpy", "shapely", "penguin_slice"}
SOURCES = sorted(PACKAGE.rglob("*.py")) + sorted((SLICE_ROOT / "scripts").glob("*.py"))


def imported_roots(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.split(".")[0]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.relative_to(SLICE_ROOT).as_posix())
def test_imports_stay_inside_the_slice_service(path):
    outside = sorted(set(imported_roots(path)) - ALLOWED)
    assert outside == [], f"{path.name} imports {outside}"


def test_the_package_does_not_shadow_a_builtin():
    import builtins
    assert not hasattr(builtins, PACKAGE.name)


def test_no_mention_of_the_original_application_in_the_code():
    for path in sorted(PACKAGE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for word in ("flask", "onshape_integration", "team_config", "TeamConfig"):
            assert word.lower() not in text.lower(), f"{path.name} mentions {word}"
