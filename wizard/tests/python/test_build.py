"""wizard/build.py: wizard/dist/index.html and the page's files, with the vendored modules, flat
in wizard/dist/assets/ under hashed names, every name inside them rewritten to its built
address, as the contract's "The wizard's built files" says."""
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


@pytest.mark.parametrize("reference, built", [
    ("src='main.js'", "src='/assets/{main}'"),
    ("src=main.js", "src=/assets/{main}"),
    ('src = "main.js"', 'src = "/assets/{main}"'),
])
def test_a_reference_in_single_quotes_or_none_is_rewritten_too(tmp_path, reference, built):
    index = f'<html><head>{VERSION_META}<script type="module" {reference}></script></head></html>'
    src = page(tmp_path, {"main.js": "export {};\n"}, index=index)
    build.build(src, tmp_path / "dist")
    html = (tmp_path / "dist" / "index.html").read_text()
    assert built.format(main=hashed("main.js", "export {};\n")) in html


def test_a_link_within_the_page_is_left_as_it_is(tmp_path):
    index = f'<html><head>{VERSION_META}<script src="main.js"></script></head><a href="#steps">Steps</a></html>'
    src = page(tmp_path, {"main.js": "export {};\n"}, index=index)
    build.build(src, tmp_path / "dist")
    assert '<a href="#steps">' in (tmp_path / "dist" / "index.html").read_text()


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
    (f"<html>{VERSION_META}<script src='https://cdn.example/x.js'></script></html>",
     "index.html loads https://cdn.example/x.js from another site"),
    (f"<html>{VERSION_META}<script src=https://cdn.example/x.js></script></html>",
     "index.html loads https://cdn.example/x.js from another site"),
    (f'<html>{VERSION_META}<script SRC = "https://cdn.example/x.js"></script></html>',
     "index.html loads https://cdn.example/x.js from another site"),
    (f"<html>{VERSION_META}<link href=//cdn.example/x.css></html>",
     "index.html loads //cdn.example/x.css from another site"),
    (f"<html>{VERSION_META}<script src='missing.js'></script></html>", "index.html names missing.js, which is not in"),
    (f"<html>{VERSION_META}<script src=missing.js></script></html>", "index.html names missing.js, which is not in"),
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


# Names inside the assets: a module's imports, a worker's, a style sheet's addresses.

def built(tmp_path, name):
    """The one built asset whose name starts with `name`'s stem and ends with its extension."""
    stem, ext = name.rsplit(".", 1)
    [path] = [p for p in (tmp_path / "dist" / "assets").iterdir()
              if re.fullmatch(re.escape(stem) + r"\.[0-9a-f]{12}\." + re.escape(ext), p.name)]
    return path


def test_a_modules_imports_are_rewritten_to_the_built_names(tmp_path):
    src = page(tmp_path, {
        "main.js": "import { a } from './steps/a.js';\nimport './side.js';\nexport { b } from \"./b.js\";\n",
        "steps/a.js": "export const a = 1;\n",
        "side.js": "export {};\n",
        "b.js": "export const b = 2;\n",
    })
    build.build(src, tmp_path / "dist")
    main = built(tmp_path, "main.js").read_text()
    assert f"from '/assets/{hashed('a.js', 'export const a = 1;\n')}';" in main
    assert f"import '/assets/{hashed('side.js', 'export {};\n')}';" in main
    assert f'from "/assets/{hashed("b.js", "export const b = 2;\n")}";' in main


def test_an_import_list_over_several_lines_is_rewritten(tmp_path):
    src = page(tmp_path, {"main.js": "import {\n  a,\n  b,\n} from '../src/lib.js';\n", "lib.js": "export const a = 1, b = 2;\n"})
    build.build(src, tmp_path / "dist")
    assert f"}} from '/assets/{hashed('lib.js', 'export const a = 1, b = 2;\n')}';" in built(tmp_path, "main.js").read_text()


def test_a_worker_and_a_dynamic_import_are_rewritten(tmp_path):
    src = page(tmp_path, {
        "main.js": "const w = new Worker(new URL('./geometry.worker.js', import.meta.url), { type: 'module' });\n"
                   "const m = await import('./late.js');\n",
        "geometry.worker.js": "import './geometry/messages.js';\n",
        "geometry/messages.js": "export {};\n",
        "late.js": "export {};\n",
    })
    build.build(src, tmp_path / "dist")
    main = built(tmp_path, "main.js").read_text()
    worker = built(tmp_path, "geometry.worker.js")
    assert f"new URL('/assets/{worker.name}', import.meta.url)" in main
    assert f"import('/assets/{hashed('late.js', 'export {};\n')}')" in main
    assert f"import '/assets/{hashed('messages.js', 'export {};\n')}';" in worker.read_text()


def test_a_name_in_a_comment_or_a_string_is_not_rewritten(tmp_path):
    text = ("// import x from './missing.js';\n/* import('./missing.js') */\n"
            "const s = \"import y from './missing.js'\";\n * remove 'a' from 'b.face'\nexport {};\n")
    src = page(tmp_path, {"main.js": text})
    build.build(src, tmp_path / "dist")
    assert built(tmp_path, "main.js").read_text() == text


def test_a_style_sheets_addresses_are_rewritten(tmp_path):
    src = page(tmp_path, {
        "css/panel.css": "@import './base.css';\n@import url(\"fonts.css\");\n"
                         ".a { background: url(../pictures/dot.svg) }\n.b { background: url('data:image/png;base64,AA==') }\n",
        "css/base.css": "p{}\n", "css/fonts.css": "q{}\n", "pictures/dot.svg": "<svg/>\n", "main.js": "export {};\n",
    })
    build.build(src, tmp_path / "dist")
    css = built(tmp_path, "panel.css").read_text()
    assert f"@import '/assets/{hashed('base.css', 'p{}\n')}';" in css
    assert f'@import url("/assets/{hashed("fonts.css", "q{}\n")}");' in css
    assert f"url(/assets/{hashed('dot.svg', '<svg/>\n')})" in css
    assert "url('data:image/png;base64,AA==')" in css


def test_a_rewritten_asset_is_named_by_the_hash_of_its_rewritten_bytes(tmp_path):
    """So a change to an imported file changes the name of every file that imports it, and a
    browser that keeps an asset for a year never mixes an old importer with a new import."""
    src = page(tmp_path, {"main.js": "import './lib.js';\n", "lib.js": "export const v = 1;\n"})
    build.build(src, tmp_path / "dist")
    first = built(tmp_path, "main.js")
    assert first.name == hashed("main.js", first.read_text())
    (src / "lib.js").write_text("export const v = 2;\n")
    build.build(src, tmp_path / "dist")
    assert built(tmp_path, "main.js").name != first.name


@pytest.mark.parametrize("text, says", [
    ("import './missing.js';\n", "main.js names ./missing.js, which is not in"),
    ("import x from 'lodash';\n", "main.js imports lodash, which is neither a file of the page nor three"),
    ("import x from 'https://cdn.example/x.js';\n", "main.js loads https://cdn.example/x.js from another site"),
    ("import x from '/elsewhere/x.js';\n", "main.js names /elsewhere/x.js by an absolute address"),
    ("const w = new Worker(new URL('../../outside.js', import.meta.url));\n", "main.js names ../../outside.js, which is not in"),
])
def test_a_module_naming_what_the_build_cannot_serve_is_refused(tmp_path, text, says):
    src = page(tmp_path, {"main.js": text})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert says in str(raised.value)


def test_a_style_sheet_loading_from_another_site_is_refused(tmp_path):
    src = page(tmp_path, {"main.js": "export {};\n", "css/panel.css": "@import url(https://fonts.example/x.css);\n"})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert "panel.css loads https://fonts.example/x.css from another site" in str(raised.value)


def test_modules_that_import_each_other_in_a_circle_are_refused_naming_them(tmp_path):
    src = page(tmp_path, {"main.js": "import './a.js';\n", "a.js": "import './b.js';\n", "b.js": "import './a.js';\n"})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert "import each other in a circle" in str(raised.value)
    assert "a.js" in str(raised.value) and "b.js" in str(raised.value)


# wizard/vendor/ built in.

def vendor_folder(tmp_path):
    vendor = tmp_path / "vendor"
    (vendor / "three" / "build").mkdir(parents=True)
    (vendor / "three" / "examples" / "jsm" / "controls").mkdir(parents=True)
    (vendor / "three" / "build" / "three.module.min.js").write_text("export const REVISION = '170';\n")
    (vendor / "three" / "examples" / "jsm" / "controls" / "OrbitControls.js").write_text(
        "import {\n\tEventDispatcher,\n} from 'three';\nexport class OrbitControls {}\n")
    (vendor / "three" / "LICENSE").write_text("MIT\n")
    (vendor / "README.md").write_text("# vendor\n")
    (vendor / ".gitignore").write_text("!build/\n")
    return vendor


def test_the_vendored_modules_are_built_in_and_three_is_named_by_its_built_address(tmp_path):
    vendor = vendor_folder(tmp_path)
    src = page(tmp_path, {"main.js": "import { OrbitControls } from '../vendor/three/examples/jsm/controls/OrbitControls.js';\n"
                                     "import * as THREE from 'three';\n"})
    build.build(src, tmp_path / "dist", vendor=vendor)
    core = built(tmp_path, "three.module.min.js")
    controls = built(tmp_path, "OrbitControls.js")
    assert core.read_text() == "export const REVISION = '170';\n"
    assert f"}} from '/assets/{core.name}';" in controls.read_text()
    main = built(tmp_path, "main.js").read_text()
    assert f"from '/assets/{controls.name}';" in main
    assert f"from '/assets/{core.name}';" in main


def test_only_the_vendored_modules_are_built_in(tmp_path):
    vendor = vendor_folder(tmp_path)
    src = page(tmp_path, {"main.js": "export {};\n"})
    build.build(src, tmp_path / "dist", vendor=vendor)
    names = sorted(re.sub(r"\.[0-9a-f]{12}\.", ".", p.name) for p in (tmp_path / "dist" / "assets").iterdir())
    assert names == ["OrbitControls.js", "main.js", "three.module.min.js"]


def test_three_without_the_vendor_folder_is_refused(tmp_path):
    src = page(tmp_path, {"main.js": "import * as THREE from 'three';\n"})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist")
    assert "main.js imports three, which is neither a file of the page nor three" in str(raised.value)


def test_a_page_file_and_a_vendored_file_of_the_same_name_are_refused(tmp_path):
    vendor = vendor_folder(tmp_path)
    src = page(tmp_path, {"main.js": "export {};\n", "OrbitControls.js": "export {};\n"})
    with pytest.raises(build.BuildError) as raised:
        build.build(src, tmp_path / "dist", vendor=vendor)
    assert "Two files would both be assets/OrbitControls.<hash>.js" in str(raised.value)


def test_the_real_page_builds_with_the_real_vendor_folder_and_every_name_resolves(tmp_path):
    build.build(WIZARD / "src", tmp_path / "dist", vendor=WIZARD / "vendor")
    assets = {p.name for p in (tmp_path / "dist" / "assets").iterdir()}
    for path in (tmp_path / "dist" / "assets").iterdir():
        if path.suffix in (".js", ".css"):
            for name in re.findall(r"/assets/([^'\")\s]+)", path.read_text(encoding="utf-8")):
                assert name in assets, f"{path.name} names /assets/{name}, which was not built"
    assert any(name.startswith("three.module.min.") for name in assets)


def test_main_builds_the_vendor_folder_in_by_default(tmp_path):
    assert build.main(["build.py", "--dist", str(tmp_path / "dist")]) == 0
    assert any(p.name.startswith("three.module.min.") for p in (tmp_path / "dist" / "assets").iterdir())
