"""The slice service stands alone: its package and scripts import only the standard library,
numpy, shapely and the package itself, and its HTTP interface (web.py, and only it) Flask and
Flask's werkzeug;
nothing of Onshape, a team configuration or another component."""
import ast
import sys

import pytest

from helpers import SLICE_ROOT

PACKAGE = SLICE_ROOT / "src" / "penguin_slice"
ALLOWED = set(sys.stdlib_module_names) | {"numpy", "shapely", "penguin_slice"}
WEB_ALLOWED = ALLOWED | {"flask", "werkzeug"}         # werkzeug: Flask's own HTTP layer (its errors)
SOURCES = sorted(PACKAGE.rglob("*.py")) + sorted((SLICE_ROOT / "scripts").glob("*.py"))


def imported_roots(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.split(".")[0]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.relative_to(SLICE_ROOT).as_posix())
def test_imports_stay_inside_the_slice_service(path):
    allowed = WEB_ALLOWED if path == PACKAGE / "web.py" else ALLOWED
    outside = sorted(set(imported_roots(path)) - allowed)
    assert outside == [], f"{path.name} imports {outside}"


def test_only_the_http_interface_imports_flask():
    importers = sorted(p.name for p in SOURCES if "flask" in set(imported_roots(p)))
    assert importers == ["web.py"]


def test_the_package_does_not_shadow_a_builtin():
    import builtins
    assert not hasattr(builtins, PACKAGE.name)


def test_no_mention_of_the_original_application_in_the_code():
    for path in sorted(PACKAGE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for word in ("onshape_integration", "team_config", "TeamConfig", "penguincam"):
            assert word.lower() not in text.lower(), f"{path.name} mentions {word}"
