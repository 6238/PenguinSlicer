"""Every file in wizard/vendor/ is listed in wizard/vendor/README.md with its SHA-256, under a
licence MIT code may include, and nothing listed is missing."""
import hashlib
import re
import subprocess
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[2] / "vendor"
ROOT = VENDOR.parents[1]
ROW = re.compile(r"^\| `([^`]+)` \| ([^|]+) \| ([^|]+) \| `([0-9a-f]{64})` \|$")
ALLOWED = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0"}


def listed():
    rows = [ROW.match(line) for line in (VENDOR / "README.md").read_text().splitlines()]
    return {m.group(1): (m.group(2).strip(), m.group(3).strip(), m.group(4)) for m in rows if m}


def test_every_vendored_file_is_listed_and_every_listed_file_is_there():
    present = sorted(str(p.relative_to(VENDOR)) for p in VENDOR.rglob("*") if p.is_file() and p.name not in ("README.md", ".gitignore"))
    assert present == sorted(listed())


def test_each_vendored_file_has_its_listed_hash():
    for path, (_, _, sha256) in listed().items():
        assert hashlib.sha256((VENDOR / path).read_bytes()).hexdigest() == sha256, path


def test_each_vendored_file_is_under_a_licence_mit_code_may_include():
    for path, (_, licence, _) in listed().items():
        assert licence in ALLOWED, f"{path}: {licence}"


def test_no_vendored_file_is_ignored_by_git_even_under_a_global_build_rule(tmp_path):
    """A machine's global excludes file often ignores `build/`, which would keep three.js's
    core (`three/build/`) out of every commit; wizard/vendor/.gitignore must win over it."""
    repo = tmp_path / "repo"
    (repo / "wizard" / "vendor").mkdir(parents=True)
    (repo / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
    (repo / "wizard" / "vendor" / ".gitignore").write_bytes((VENDOR / ".gitignore").read_bytes())
    global_excludes = tmp_path / "global-excludes"
    global_excludes.write_text("build/\n")
    git = ["git", "-c", f"core.excludesFile={global_excludes}", "-C", str(repo)]
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)
    paths = [f"wizard/vendor/{path}" for path in listed()]
    for path in paths:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("")
    result = subprocess.run([*git, "check-ignore", "--", *paths], capture_output=True, text=True, timeout=30)
    assert result.stdout.split() == [], "ignored by git: " + " ".join(result.stdout.split())
    assert result.returncode == 1, result.stderr


def test_three_js_is_the_listed_release():
    head = (VENDOR / "three" / "build" / "three.module.min.js").read_text()[:200]
    versions = {version for version, _, _ in listed().values() if version.startswith("three.js")}
    assert versions == {"three.js 0.170.0"}
    assert 'const t="170"' in head
