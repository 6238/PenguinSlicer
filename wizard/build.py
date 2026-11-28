#!/usr/bin/env python3
"""Build wizard/dist/ from wizard/src/ and wizard/vendor/, as the contract's "The wizard's built
files" says.

`wizard/dist/index.html` is the page; every other file of `wizard/src/`, and every module
(`.js`) of `wizard/vendor/`, goes flat into `wizard/dist/assets/` as
`<name>.<first 12 hexadecimal characters of its SHA-256>.<extension>`.

Names are rewritten to built addresses, `/assets/<built name>`:
- in index.html, each `src` or `href` (its value in double quotes, single quotes or none) that
  names a file of `wizard/src/`; a link within the page (`#...`) is left as it is;
- in a module, each static `import`/`export ... from`, each `import('...')` and each
  `new URL('...', import.meta.url)` (how a page starts a worker), outside comments and strings;
  the bare name `three` is the vendored core, `vendor/three/build/three.module.min.js`;
- in a style sheet, each `@import` and `url(...)`, except `data:` addresses.
A file's hash is taken of its bytes after its names are rewritten, so a change to a module
changes the name of every module that imports it. A file with nothing to rewrite keeps its
bytes unchanged.

The build refuses, saying why: no index.html; a page with no version placeholder or with more
than one; a reference to another site; a reference to a file that is not in `wizard/src/` or,
for a module, `wizard/vendor/`; an absolute address; a bare module name other than `three`;
modules that import each other in a circle; two files that would get the same built name.

Usage: build.py [--src FOLDER] [--dist FOLDER] [--vendor FOLDER]
"""
import argparse
import hashlib
import posixpath
import re
import shutil
import sys
from pathlib import Path

WIZARD = Path(__file__).resolve().parent
PLACEHOLDER = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">'
# A src or href attribute with its value in double quotes, single quotes or none, as HTML
# allows: group 1 is up to the value's opening quote, group 2 the value, group 3 the closing
# quote (empty when there is none).
REFERENCE = re.compile(
    r"""(\s(?:src|href)\s*=\s*)(?:"([^"]*)(")|'([^']*)(')|([^\s"'=<>`]+)())""", re.IGNORECASE)
OTHER_SITE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)
THREE_CORE = "three/build/three.module.min.js"          # inside the vendor folder

# A module's names, each with its specifier as group "q" (the quote) and "s" (the specifier).
MODULE_NAMES = [
    # import x from '...'; import {a, b} from '...'; export ... from '...', over several lines
    re.compile(r"""(?m)^[ \t]*(?:import|export)\b[^'"`;]*?\bfrom\s*(?P<q>['"])(?P<s>[^'"\n]+)(?P=q)"""),
    # import '...';
    re.compile(r"""(?m)^[ \t]*import\s*(?P<q>['"])(?P<s>[^'"\n]+)(?P=q)"""),
    # import('...')
    re.compile(r"""\bimport\s*\(\s*(?P<q>['"])(?P<s>[^'"\n]+)(?P=q)\s*\)"""),
    # new URL('...', import.meta.url)
    re.compile(r"""\bnew\s+URL\s*\(\s*(?P<q>['"])(?P<s>[^'"\n]+)(?P=q)\s*,\s*import\.meta\.url\s*\)"""),
]
# A style sheet's names: @import '...' and url(...), quoted or not.
STYLE_NAMES = [
    re.compile(r"""@import\s+(?P<q>['"])(?P<s>[^'"\n]+)(?P=q)"""),
    re.compile(r"""\burl\(\s*(?P<q>['"]?)(?P<s>[^'")\s]+)(?P=q)\s*\)"""),
]


class BuildError(Exception):
    pass


def built_name(name, data):
    path = Path(name)
    return f"{path.stem}.{hashlib.sha256(data).hexdigest()[:12]}{path.suffix}"


# A '/' starts a regular expression literal, not a division, after one of these characters,
# after one of these words, or at the start of the text: the usual rule of thumb.
BEFORE_REGEX = set("(,=:[!&|?{};+-*%<>~^")
WORD_BEFORE_REGEX = re.compile(r"(?:^|[^\w$])(?:return|typeof|instanceof|case|do|else|in|of|new|delete|void|throw|yield|await)$")


def code_only(text):
    """The text with every comment, string and template literal blanked to spaces, newlines
    and the outer quotes kept, so that each position is the same as in the text. The quotes
    of a string stay, and its contents become spaces: a name is found by its position in the
    blanked text and read from the original. Regular expression literals are blanked too."""
    out = []
    i, n = 0, len(text)

    def before():
        return "".join(out[-200:]).rstrip()

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif c == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            stop = n if end == -1 else end + 2
            out.extend("\n" if ch == "\n" else " " for ch in text[i:stop])
            i = stop
        elif c in "\"'`":
            out.append(c)
            i += 1
            while i < n and text[i] != c:
                if text[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    i += 1
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(c)
                i += 1
        elif c == "/" and (before() == "" or before()[-1] in BEFORE_REGEX or WORD_BEFORE_REGEX.search(before())):
            end, in_class, j = -1, False, i + 1
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "/" and not in_class:
                    end = j + 1
                    break
                j += 1
            if end == -1:
                out.append(c)
                i += 1
            else:
                out.append("/" + " " * (end - i - 2) + "/")
                i = end
        else:
            out.append(c)
            i += 1
    return "".join(out)


def specifiers(path, text):
    """Each name a module or style sheet carries, as (start, end, specifier) of the specifier
    in the text."""
    found = []
    if path.suffix in (".js", ".mjs"):
        # A specifier is a string, so it is blanked in code_only; the statement around it is
        # not. Match on a copy whose strings are blank, then read the specifier at the same
        # place in the text.
        blank = code_only(text)
        for pattern in MODULE_NAMES:
            loose = re.compile(pattern.pattern.replace("[^'\"\\n]+", "[^'\"\\n]*?"))
            for match in loose.finditer(blank):
                start, end = match.span("s")
                quote = match.group("q")
                # the blanked string runs from the opening quote to the closing one
                close = text.find(quote, start)
                found.append((start, close, text[start:close]))
    elif path.suffix == ".css":
        for pattern in STYLE_NAMES:
            for match in pattern.finditer(text):
                found.append((match.start("s"), match.end("s"), match.group("s")))
    return sorted(set(found))


def build(src, dist, vendor=None):
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

    # Every file to build, by its source path: the shown name (relative to src, or
    # "vendor/..." for a vendored module).
    files = {}
    for path in sorted(p for p in src.rglob("*") if p.is_file() and p != index):
        files[path.resolve()] = path.relative_to(src).as_posix()
    if vendor is not None:
        vendor = Path(vendor)
        for path in sorted(p for p in vendor.rglob("*.js") if p.is_file()):
            files[path.resolve()] = "vendor/" + path.relative_to(vendor).as_posix()
    owners = {}
    for path, shown in files.items():
        key = f"{path.stem}.<hash>{path.suffix}"
        if key in owners:
            raise BuildError(f"Two files would both be assets/{key}: {owners[key]} and {shown}")
        owners[key] = shown
    core = (vendor / THREE_CORE).resolve() if vendor is not None else None

    def target(path, shown, spec):
        """The source file a name inside `path` stands for."""
        if OTHER_SITE.match(spec):
            raise BuildError(f"{shown} loads {spec} from another site; the page loads nothing from another site")
        if spec.startswith("/"):
            raise BuildError(f"{shown} names {spec} by an absolute address; name a file by its path from {shown}")
        if not spec.startswith("."):
            if path.suffix in (".js", ".mjs"):
                if spec == "three" and core is not None and core in files:
                    return core
                raise BuildError(f"{shown} imports {spec}, which is neither a file of the page nor three")
        resolved = (path.parent / spec.split("?")[0].split("#")[0]).resolve()
        if resolved not in files:
            raise BuildError(f"{shown} names {spec}, which is not in {src}" + (f" or {vendor}" if vendor else ""))
        return resolved

    texts = {}                                    # path: (text, [(start, end, target)])
    for path, shown in files.items():
        if path.suffix not in (".js", ".mjs", ".css"):
            continue
        text = path.read_text(encoding="utf-8")
        names = []
        for start, end, spec in specifiers(path, text):
            if spec.startswith("data:") or spec.startswith("#"):
                continue
            names.append((start, end, target(path, shown, spec)))
        if names:
            texts[path] = (text, names)

    names = {}                                    # path: built name
    contents = {}                                 # path: built bytes

    def name_of(path, visiting):
        if path in names:
            return names[path]
        if path in visiting:
            circle = [files[p] for p in visiting[visiting.index(path):]] + [files[path]]
            raise BuildError("These modules import each other in a circle, so no name can carry the hash of "
                             "what it imports: " + " -> ".join(circle))
        if path in texts:
            text, refs = texts[path]
            pieces, last = [], 0
            for start, end, other in refs:
                pieces.append(text[last:start])
                pieces.append("/assets/" + name_of(other, visiting + [path]))
                last = end
            pieces.append(text[last:])
            data = "".join(pieces).encode("utf-8")
        else:
            data = path.read_bytes()
        contents[path] = data
        names[path] = built_name(path.name, data)
        return names[path]

    for path in files:
        name_of(path, [])

    by_shown = {shown: names[path] for path, shown in files.items()}

    def replace(match):
        start = match.group(1)
        value, quote = next((match.group(i), match.group(i + 1)) for i in (2, 4, 6) if match.group(i) is not None)
        opening = match.group(0)[len(start)] if quote else ""
        if OTHER_SITE.match(value):
            raise BuildError(f"index.html loads {value} from another site; the page loads nothing from another site")
        if value.startswith("#"):
            return match.group(0)                 # a link within the page
        normal = posixpath.normpath(value)
        if value.startswith("/") or normal.startswith("..") or normal.startswith("vendor/") or normal not in by_shown:
            raise BuildError(f"index.html names {value}, which is not in {src}")
        return f"{start}{opening}/assets/{by_shown[normal]}{quote}"

    built_html = REFERENCE.sub(replace, html)

    shutil.rmtree(dist / "assets", ignore_errors=True)
    (dist / "assets").mkdir(parents=True)
    for path, name in names.items():
        (dist / "assets" / name).write_bytes(contents[path])
    (dist / "index.html").write_text(built_html, encoding="utf-8")
    return by_shown


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", default=str(WIZARD / "src"))
    parser.add_argument("--dist", default=str(WIZARD / "dist"))
    parser.add_argument("--vendor", default=str(WIZARD / "vendor"))
    args = parser.parse_args(argv[1:])
    try:
        assets = build(args.src, args.dist, vendor=args.vendor)
    except BuildError as error:
        print(f"build: {error}", file=sys.stderr)
        return 1
    print(f"build: wrote {Path(args.dist) / 'index.html'} and {len(assets)} assets")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
