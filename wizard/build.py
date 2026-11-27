#!/usr/bin/env python3
"""Build wizard/dist/ from wizard/src/, as the contract's "The wizard's built files" says.

`wizard/dist/index.html` is the page; every other file of `wizard/src/` goes flat into
`wizard/dist/assets/` as `<name>.<first 12 hexadecimal characters of its SHA-256>.<extension>`,
its bytes unchanged, and each `src="..."` or `href="..."` of index.html that names one of them
becomes `/assets/<that name>`. The build refuses, saying why: a page with no version
placeholder or with more than one, a reference to a file that is not in `wizard/src/`, a
reference to another site, and two files that would get the same built name.

As far as phase 2's first batch builds it: names inside an asset (a module's imports, a
worker's, a style sheet's) are not yet rewritten, and `wizard/vendor/` is not yet built in;
the skeleton batch adds both. Usage: build.py [--src FOLDER] [--dist FOLDER].
"""
import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

WIZARD = Path(__file__).resolve().parent
PLACEHOLDER = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">'
REFERENCE = re.compile(r'(\s(?:src|href)=")([^"]*)(")', re.IGNORECASE)
OTHER_SITE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)


class BuildError(Exception):
    pass


def built_name(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{path.stem}.{digest}{path.suffix}"


def build(src, dist):
    src, dist = Path(src), Path(dist)
    index = src / "index.html"
    if not index.is_file():
        raise BuildError(f"No index.html in {src}")
    html = index.read_text(encoding="utf-8")
    count = html.count(PLACEHOLDER)
    if count == 0:
        raise BuildError("index.html has no version placeholder: " + PLACEHOLDER)
    if count > 1:
        raise BuildError(f"index.html has the version placeholder {count} times; the front server fills in one")

    assets = {}                                   # path relative to src, '/' between folders: built name
    owners = {}                                   # built name with <hash>: the first file that takes it
    for path in sorted(p for p in src.rglob("*") if p.is_file() and p != index):
        relative = path.relative_to(src).as_posix()
        key = f"{path.stem}.<hash>{path.suffix}"
        if key in owners:
            raise BuildError(f"Two files would both be assets/{key}: {owners[key]} and {relative}")
        owners[key] = relative
        assets[relative] = built_name(path)

    def replace(match):
        value = match.group(2)
        if OTHER_SITE.match(value):
            raise BuildError(f"index.html loads {value} from another site; the page loads nothing from another site")
        if value not in assets:
            raise BuildError(f"index.html names {value}, which is not in {src}")
        return f"{match.group(1)}/assets/{assets[value]}{match.group(3)}"

    built_html = REFERENCE.sub(replace, html)

    shutil.rmtree(dist / "assets", ignore_errors=True)
    (dist / "assets").mkdir(parents=True)
    for relative, name in assets.items():
        shutil.copyfile(src / relative, dist / "assets" / name)
    (dist / "index.html").write_text(built_html, encoding="utf-8")
    return assets


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", default=str(WIZARD / "src"))
    parser.add_argument("--dist", default=str(WIZARD / "dist"))
    args = parser.parse_args(argv[1:])
    try:
        assets = build(args.src, args.dist)
    except BuildError as error:
        print(f"build: {error}", file=sys.stderr)
        return 1
    print(f"build: wrote {Path(args.dist) / 'index.html'} and {len(assets)} assets")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
