"""wizard/build.py, as far as this batch builds it: wizard/dist/index.html and the page's files
flat in wizard/dist/assets/ under hashed names, as the contract's "The wizard's built files"
says."""
import hashlib
import re
from pathlib import Path

import pytest

import build

WIZARD = Path(__file__).resolve().parents[2]
VERSION_META = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">'


def page(tmp_path, files, index=None):
    src = tmp_path / "src"
    for name, text in files.items():
        (src / name).parent.mkdir(parents=True, exist_ok=True)
        (src / name).write_text(text)
    if index is None:
        style = '<link rel="stylesheet" href="css/panel.css">' if "css/panel.css" in files else ""
        index = f'<html><head>{VERSION_META}<script type="module" src="main.js"></script>{style}</head></html>'
    (src / "index.html").write_text(index)
    return src


def hashed(name, text):
    stem, ext = name.rsplit(".", 1)
    return f"{stem}.{hashlib.sha256(text.encode()).hexdigest()[:12]}.{ext}"


def test_each_file_gets_its_hashed_name_flat_in_assets(tmp_path):
    src = page(tmp_path, {"main.js": "export {};\n", "css/panel.css": "body{}\n"})
    build.build(src, tmp_path / "dist")
    assets = sorted(p.name for p in (tmp_path / "dist" / "assets").iterdir())
    assert assets == sorted([hashed("main.js", "export {};\n"), hashed("panel.css", "body{}\n")])
    for name in assets:
        assert re.fullmatch(r"[A-Za-z0-9_-]+\.[0-9a-f]{12}\.[a-z0-9]+", name)


def test_index_html_names_each_asset_by_its_built_address(tmp_path):
    src = page(tmp_path, {"main.js": "export {};\n", "css/panel.css": "body{}\n"})
    build.build(src, tmp_path / "dist")
    html = (tmp_path / "dist" / "index.html").read_text()
    assert f'src="/assets/{hashed("main.js", "export {};\n")}"' in html
    assert f'href="/assets/{hashed("panel.css", "body{}\n")}"' in html
    assert html.count(VERSION_META) == 1


def test_the_bytes_of_each_asset_are_unchanged(tmp_path):
    src = page(tmp_path, {"main.js": "export const a = 'é';\n"})
    build.build(src, tmp_path / "dist")
    [asset] = (tmp_path / "dist" / "assets").iterdir()
    assert asset.read_bytes() == (src / "main.js").read_bytes()


def test_building_twice_gives_the_same_files_and_drops_stale_ones(tmp_path):
    src = page(tmp_path, {"main.js": "export {};\n"})
    dist = tmp_path / "dist"
    build.build(src, dist)
    (dist / "assets" / "old.0123456789ab.js").write_text("stale")
    build.build(src, dist)
    assert sorted(p.name for p in (dist / "assets").iterdir()) == [hashed("main.js", "export {};\n")]


def test_the_real_page_builds(tmp_path):
    build.build(WIZARD / "src", tmp_path / "dist")
    html = (tmp_path / "dist" / "index.html").read_text()
    assert html.count(VERSION_META) == 1
    assert re.search(r'src="/assets/main\.[0-9a-f]{12}\.js"', html)


@pytest.mark.parametrize("index, says", [
    ("<html><head></head></html>", "index.html has no version placeholder"),
    (f"<html>{VERSION_META}{VERSION_META}</html>", "index.html has the version placeholder 2 times"),
    (f'<html>{VERSION_META}<script src="missing.js"></script></html>', "index.html names missing.js, which is not in"),
    (f'<html>{VERSION_META}<script src="https://cdn.example/x.js"></script></html>',
     "index.html loads https://cdn.example/x.js from another site"),
    (f'<html>{VERSION_META}<link href="//cdn.example/x.css"></html>',
     "index.html loads //cdn.example/x.css from another site"),
    (f'<html>{VERSION_META}<script src="../secret.js"></script></html>', "index.html names ../secret.js, which is not in"),
])
def test_a_page_the_contract_forbids_is_refused_saying_why(tmp_path, index, says):
    src = page(tmp_path, {"main.js": "export {};\n"}, index=index)
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert says in str(raised.value)


def test_two_files_of_the_same_name_are_refused_naming_both(tmp_path):
    src = page(tmp_path, {"main.js": "a\n", "steps/main.js": "b\n"})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert str(raised.value) == "Two files would both be assets/main.<hash>.js: main.js and steps/main.js"


def test_a_folder_without_index_html_is_refused(tmp_path):
    (tmp_path / "src").mkdir()
    with pytest.raises(build.BuildError) as raised:
        build.build(tmp_path / "src", tmp_path / "dist")
    assert str(raised.value) == f"No index.html in {tmp_path / 'src'}"


def test_main_reports_a_refusal_and_fails(tmp_path, capsys):
    (tmp_path / "src").mkdir()
    assert build.main(["build.py", "--src", str(tmp_path / "src"), "--dist", str(tmp_path / "dist")]) == 1
    assert capsys.readouterr().err.strip() == f"build: No index.html in {tmp_path / 'src'}"


def test_main_builds(tmp_path, capsys):
    src = page(tmp_path, {"main.js": "export {};\n"})
    assert build.main(["build.py", "--src", str(src), "--dist", str(tmp_path / "dist")]) == 0
    assert (tmp_path / "dist" / "index.html").is_file()
