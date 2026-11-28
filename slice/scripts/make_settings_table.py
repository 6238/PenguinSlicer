#!/usr/bin/env python3
"""Generate the table of settings, src/penguin_slice/settings/table.json, from Orca's source.

The table ([contracts/settings-table.md](../../contracts/settings-table.md)) describes every
process setting a plate configuration may replace. It is made, never written by hand, from:

- Orca's source for the pinned version (tools/orca-source/, fetched and verified by
  scripts/fetch_orca_source.py): the list of process settings (src/libslic3r/Preset.cpp,
  `s_Preset_print_options`), each setting's definition (src/libslic3r/PrintConfig.cpp: its
  type, label, explanation, unit, least and greatest values, choices and default) and the
  pages and setting groups Orca shows them on, in Orca's order (src/slic3r/GUI/Tab.cpp,
  `TabPrint::build`), and which settings Orca keeps for each extruder variant
  (`print_options_with_variant`);
- the classification (src/penguin_slice/settings/classification.json): every process setting
  of the pinned Orca as a parameter, as programmatic or as not offered, each of the last two
  with its reason; only parameters enter the table;
- the profile catalog (src/penguin_slice/profiles/catalog/): each process profile's value of
  each setting, and the catalog's names.

The source is read as data: nothing of Orca's code is copied into PenguinSlicer (Orca is
AGPL, PenguinSlicer MIT). A setting classified nowhere, a classified setting this Orca does
not have, or a definition the reader cannot read stops the generator with a message naming
the setting. `--check` compares instead of writing, and fails when the checked-in table
differs from what the generator makes. Standard library only.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SLICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SLICE_ROOT / "src" / "penguin_slice"
SOURCE_DIR = SLICE_ROOT / "tools" / "orca-source"
CATALOG_DIR = PACKAGE / "profiles" / "catalog"
CLASSIFICATION = PACKAGE / "settings" / "classification.json"
TABLE = PACKAGE / "settings" / "table.json"

FORMAT = 1
# The three files of Orca's source the table is read from, relative to the source's root.
SOURCE_FILES = {
    "options": "src/libslic3r/Preset.cpp",
    "definitions": "src/libslic3r/PrintConfig.cpp",
    "pages": "src/slic3r/GUI/Tab.cpp",
}
CLASSES = ("parameters", "programmatic", "not_offered")

# Orca's option type -> (kind, number_form); a type ending in "s" is a list of the same.
KINDS = {
    "coFloat": ("number", "decimal"),
    "coInt": ("number", "integer"),
    "coPercent": ("number", "percent"),
    "coFloatOrPercent": ("number", "decimal_or_percent"),
    "coBool": ("choice", None),
    "coEnum": ("choice", None),
    "coString": ("text", None),
}
LIST_TYPES = {"coFloats": "coFloat", "coInts": "coInt", "coPercents": "coPercent",
              "coFloatsOrPercents": "coFloatOrPercent", "coBools": "coBool", "coStrings": "coString"}
ON_AND_OFF = [{"value": "0", "label": "Off"}, {"value": "1", "label": "On"}]


class TableError(Exception):
    """The table cannot be made; the message names the setting or the file and why."""


# --- Reading C++ as data -------------------------------------------------------------

def strip_comments(text):
    """`text` without its // and /* */ comments; string and character literals kept whole.
    A block comment becomes one space, a line comment ends before its newline."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            out.append(" ")
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


_STRING = re.compile(r'(?:u8)?"((?:[^"\\]|\\.)*)"', re.S)
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\", "r": "\r", "0": "\0"}


def _unescape(body):
    def one(match):
        esc = match.group(1)
        if esc[0] == "u":
            return chr(int(esc[1:], 16))
        return _ESCAPES[esc]
    return re.sub(r'\\(u[0-9a-fA-F]{4}|[nt"\'\\r0])', one, body)


def cpp_string(expr, name):
    """The text of a C++ string expression made only of literals, `L(...)` around them and
    `+` between them; anything else (a function call, a variable) is refused naming `name`."""
    rest = _STRING.sub("", expr)
    rest = re.sub(r"\b(?:L|_L|_u8L)\s*\(", "", rest)
    if re.sub(r"[\s()+]", "", rest):
        raise TableError(f"{name}: cannot read the text {expr.strip()[:120]!r}: it is not made of string literals")
    return "".join(_unescape(m.group(1)) for m in _STRING.finditer(expr))


def _statements(block, separator=";"):
    """The block split at each `separator` outside strings and brackets."""
    out, start, depth, i, n = [], 0, 0, 0, len(block)
    while i < n:
        c = block[i]
        if c == '"':
            j = i + 1
            while j < n and block[j] != '"':
                j += 2 if block[j] == "\\" else 1
            i = j + 1
            continue
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
        elif c == separator and depth == 0:
            out.append(block[start:i].strip())
            start = i + 1
        i += 1
    tail = block[start:].strip()
    if tail:
        out.append(tail)
    return out


def _number(expr, name, what, constants=None):
    """A number literal, or a named constant of the file, with an optional sign."""
    text = expr.strip()
    sign, bare = (-1, text[1:].strip()) if text.startswith("-") else (1, text)
    try:
        value = sign * (constants or {})[bare] if bare in (constants or {}) else float(text.rstrip("f"))
    except ValueError:
        raise TableError(f"{name}: cannot read its {what} {text[:60]!r}") from None
    return int(value) if value == int(value) else value


def _constants(text):
    """{name: value} of the file's `const int|double NAME = <number>;` lines."""
    return {name: float(value) for name, value in
            re.findall(r'\bconst\s+(?:int|double|float)\s+(\w+)\s*=\s*(-?[0-9.]+)\s*;', text)}


@dataclass
class Definition:
    """One of Orca's option definitions, as far as the table needs it."""
    name: str
    type: str
    label: str = ""
    full_label: str = ""
    tooltip: str = ""
    sidetext: str = ""
    min: float | None = None
    max: float | None = None
    enum_values: list = field(default_factory=list)
    enum_labels: list = field(default_factory=list)
    default: str | None = None        # the C++ expression given to set_default_value
    problems: list = field(default_factory=list)     # lines of it the reader could not read

    # What a definition may take over from another (`def->sidetext = other->sidetext`).
    COPIED = ("label", "full_label", "tooltip", "sidetext", "min", "max", "enum_values", "enum_labels")


_ADD = re.compile(r'(?:\b(\w+)\s*=\s*)?\bdef\s*=\s*this->add(?:_nullable)?\(\s*"([^"]+)"\s*,\s*(co\w+)\s*\)\s*;')
_ANY_DEF = re.compile(r'\bdef\s*=')
_ATTR = re.compile(r'^def->(label|full_label|tooltip|sidetext|min|max)\s*=\s*(.*)$', re.S)
_PUSH = re.compile(r'^def->(enum_values|enum_labels)\.(?:push_back|emplace_back)\s*\((.*)\)$', re.S)
_LIST = re.compile(r'^def->(enum_values|enum_labels)\s*=\s*(.*)$', re.S)
_COPY = re.compile(r'^def->(\w+)\s*=\s*(\w+)->(\w+)$')
_DEFAULT = re.compile(r'^def->set_default_value\s*\((.*)\)$', re.S)


def _split_list(expr, name):
    """The strings of a braced list `{L("a"), "b"}`."""
    inner = expr.strip()
    if not (inner.startswith("{") and inner.endswith("}")):
        raise TableError(f"{name}: cannot read the list {inner[:80]!r}")
    items = [s for s in _statements(inner[1:-1], ",") if s]
    return [cpp_string(item, name) for item in items]


def read_definitions(text):
    """{name: Definition} for every option added under a literal name. A definition's lines
    run from its `def = this->add(...)` to the next assignment of `def`, so the lines of an
    option added under a computed name (in a loop) are nobody's. Choices taken over from
    another definition (`def->enum_values = other->enum_values`) are that definition's."""
    text = strip_comments(text)
    constants = _constants(text)
    defs, aliases, copies = {}, {}, []
    for match in _ADD.finditer(text):
        alias, name, type_ = match.groups()
        if alias and alias != "def":
            aliases[alias] = name
        end = _ANY_DEF.search(text, match.end())
        block = text[match.end():end.start() if end else len(text)]
        definition = Definition(name, type_)
        for statement in _statements(block):
            try:
                if (m := _COPY.match(statement)) and m.group(1) in Definition.COPIED:
                    copies.append((definition, m.group(1), m.group(2), m.group(3)))
                elif m := _ATTR.match(statement):
                    attr, expr = m.groups()
                    if attr in ("min", "max"):
                        setattr(definition, attr, _number(expr, name, attr, constants))
                    else:
                        setattr(definition, attr, cpp_string(expr, name))
                elif m := _PUSH.match(statement):
                    getattr(definition, m.group(1)).append(cpp_string(m.group(2), name))
                elif m := _LIST.match(statement):
                    setattr(definition, m.group(1), _split_list(m.group(2), name))
                elif m := _DEFAULT.match(statement):
                    definition.default = m.group(1).strip()
            except TableError as exc:     # only a setting the table needs is refused for it
                definition.problems.append(str(exc))
        defs[name] = definition
    for definition, attr, alias, source_attr in copies:
        source = defs.get(aliases.get(alias, ""))
        if source is None:
            definition.problems.append(f"{definition.name}: its {attr} comes from {alias}, which names no definition")
        else:
            value = getattr(source, source_attr, None)
            setattr(definition, attr, list(value) if isinstance(value, list) else value)
    return defs


def read_enum_keys(text):
    """{enum type: {constant: key}} from the `s_keys_map_<Type>` tables."""
    text = strip_comments(text)
    maps = {}
    for match in re.finditer(r'\bs_keys_map_(\w+)\s*=?\s*\{(.*?)\};', text, re.S):
        pairs = re.findall(r'\{\s*"([^"]*)"\s*,\s*(?:int\s*\(\s*)?(?:\w+::)*(\w+)\s*\)?\s*\}', match.group(2))
        maps[match.group(1)] = {constant: key for key, constant in pairs}
    return maps


def read_process_options(text):
    """The process settings, in Orca's order, from `s_Preset_print_options`."""
    match = re.search(r's_Preset_print_options\s*\{(.*?)\};', text, re.S)
    if not match:
        raise TableError("the list of process settings (s_Preset_print_options) is not in Preset.cpp")
    return re.findall(r'"([^"]+)"', strip_comments(match.group(1)))


def read_variant_options(text):
    """The process settings Orca keeps one value of for each extruder variant."""
    match = re.search(r'print_options_with_variant\s*=\s*\{(.*?)\};', strip_comments(text), re.S)
    if not match:
        raise TableError("the list of variant settings (print_options_with_variant) is not in PrintConfig.cpp")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


_PAGE = re.compile(r'add_options_page\(\s*L\("([^"]+)"\)')
_GROUP = re.compile(r'new_optgroup\(\s*L\("([^"]+)"\)')
_OPTION = re.compile(r'(?:append_single_option_line|get_option)\(\s*"([^"]+)"')


def read_pages(text):
    """[(page, group, name)] of Orca's process settings, in the order Orca shows them, from
    TabPrint::build; a commented line shows nothing."""
    start = text.find("void TabPrint::build()")
    if start < 0:
        raise TableError("the pages of process settings (TabPrint::build) are not in Tab.cpp")
    end = text.find("\nvoid ", start + 1)
    body = strip_comments(text[start:end if end > 0 else len(text)])
    found, page, group = [], None, None
    for match in re.finditer("|".join(f"(?:{p.pattern})" for p in (_PAGE, _GROUP, _OPTION)), body):
        page_name, group_name, option = match.groups()
        if page_name:
            page, group = page_name, None
        elif group_name:
            group = group_name
        elif option not in (name for _p, _g, name in found):
            found.append((page, group, option))
    return found


# --- Values as Orca writes them -------------------------------------------------------

def _figure(value):
    """A number as Orca's serialize writes it (an ostream's default, six significant digits),
    from a C++ literal (`0.`, `0.5f`, `-1`)."""
    text = str(value).strip()
    if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?[fF]?", text):
        text = text.rstrip("fF")
    return f"{float(text):.6g}"


def default_value(definition, enum_keys):
    """Orca's default of a setting, as the string Orca writes it in a profile."""
    expr = definition.default
    m = re.fullmatch(r'new\s+ConfigOption(\w+?)(?:<(\w+)>)?\s*[({]\s*(.*?)\s*[)}]', expr or "", re.S)
    if not m:
        raise TableError(f"{definition.name}: cannot read its default {str(expr)[:80]!r}")
    kind, enum_type, args = m.groups()
    kind = re.sub(r"Nullable$", "", kind)
    first = args.split(",")[0].strip() if args else ""
    try:
        if kind in ("Float", "Floats", "Int", "Ints"):
            return _figure(first or 0)
        if kind in ("Percent", "Percents"):
            return _figure(first or 0) + "%"
        if kind == "FloatOrPercent":
            value, percent = [a.strip() for a in args.split(",")]
            return _figure(value) + ("%" if percent == "true" else "")
        if kind in ("Bool", "Bools"):
            return {"true": "1", "false": "0", "1": "1", "0": "0"}[first]
        if kind == "Enum":
            constant = first.split("::")[-1]
            return enum_keys[enum_type][constant]
        if kind == "String":
            return cpp_string(args, definition.name) if args else ""
    except (KeyError, ValueError):
        pass
    raise TableError(f"{definition.name}: cannot read its default {expr[:80]!r}")


# --- The table -----------------------------------------------------------------------

def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TableError(f"cannot read {path}: {exc.strerror}; run `make -C slice orca-source`") from None


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TableError(f"cannot read {path}: {exc}") from None


def read_classification(path, options):
    """{name: class} for every process setting, checked against Orca's list `options`."""
    data = _json(path)
    seen, twice = {}, []
    for cls in CLASSES:
        group = data.get(cls, [])
        for name in group:
            if cls != "parameters" and not str(group[name]).strip():
                raise TableError(f"{name}: no reason given for classifying it {cls} in {path}")
            if name in seen:
                twice.append(name)
            seen[name] = cls
    if twice:
        raise TableError(f"settings classified more than once in {path}: {', '.join(sorted(set(twice)))}")
    missing = [name for name in options if name not in seen]
    if missing:
        raise TableError(f"process settings of this Orca classified nowhere (classify each in {path} as a "
                         f"parameter, programmatic or not offered): {', '.join(missing)}")
    gone = sorted(set(seen) - set(options))
    if gone:
        raise TableError(f"classified in {path} but not a process setting of this Orca: {', '.join(gone)}")
    return seen


def _entry(definition, page, group, per_variant):
    name, type_ = definition.name, definition.type
    if type_ in LIST_TYPES:
        if not per_variant:
            raise TableError(f"{name}: a list of values ({type_}) that Orca does not keep for each extruder "
                             f"variant, which the table cannot hold; classify it not offered")
        type_ = LIST_TYPES[type_]
    if type_ not in KINDS:
        raise TableError(f"{name}: Orca's type {type_} is none of the table's kinds; classify it not offered")
    kind, number_form = KINDS[type_]
    label = definition.label or definition.full_label
    if not label:
        raise TableError(f"{name}: Orca gives it no label")
    entry = {"name": name, "kind": kind, "label": label, "section": page, "group": group,
             "explanation": definition.tooltip}
    if definition.sidetext:
        entry["unit"] = definition.sidetext
    entry["per_variant"] = per_variant
    if type_ == "coBool":
        entry["choices"] = list(ON_AND_OFF)
    elif type_ == "coEnum":
        if not definition.enum_values or len(definition.enum_values) != len(definition.enum_labels):
            raise TableError(f"{name}: its choices and their labels do not pair up")
        entry["choices"] = [{"value": v, "label": lab} for v, lab in zip(definition.enum_values, definition.enum_labels)]
    elif kind == "number":
        entry["number_form"] = number_form
        for bound in ("min", "max"):
            value = getattr(definition, bound)
            if value is not None:
                entry[bound] = value
    return entry


def _variant_of(printer):
    """The extruder variant a printer profile uses, as a process profile names it."""
    def first(key):
        value = printer.get(key, "")
        return value[0] if isinstance(value, list) and value else value
    return f"{first('extruder_type')} {first('nozzle_volume_type')}".strip()


def _corners(area, name):
    try:
        return [[_plain(float(v)) for v in corner.split("x")] for corner in area]
    except (AttributeError, ValueError):
        raise TableError(f"printer {name}: cannot read its printable_area {area!r}") from None


def _plain(value):
    return int(value) if value == int(value) else value


def build_table(source_dir=SOURCE_DIR, catalog_dir=CATALOG_DIR, classification=CLASSIFICATION):
    """The table of settings, as a dict in the contract's shape."""
    source_dir, catalog_dir = Path(source_dir), Path(catalog_dir)
    texts = {key: _read(source_dir / rel) for key, rel in SOURCE_FILES.items()}
    options = read_process_options(texts["options"])
    classes = read_classification(classification, options)
    definitions = read_definitions(texts["definitions"])
    enum_keys = read_enum_keys(texts["definitions"])
    variants = read_variant_options(texts["definitions"])
    shown = {name: (page, group) for page, group, name in read_pages(texts["pages"])}

    settings = []
    for name in options:
        if classes[name] != "parameters":
            continue
        if name not in definitions:
            raise TableError(f"{name}: no definition of it in PrintConfig.cpp")
        if name not in shown:
            raise TableError(f"{name}: on no page of Orca's process settings; classify it not offered")
        if definitions[name].problems:
            raise TableError(definitions[name].problems[0])
        settings.append(_entry(definitions[name], *shown[name], name in variants))
    order = {name: i for i, (_p, _g, name) in enumerate(read_pages(texts["pages"]))}
    settings.sort(key=lambda e: order[e["name"]])

    index = _json(catalog_dir / "index.json")
    printers = {e["name"]: _json(catalog_dir / e["file"]) for e in index.get("printers", [])}
    process_values = {}
    for item in index.get("processes", []):
        profile = _json(catalog_dir / item["file"])
        printer = printers.get((item.get("compatible_printers") or [None])[0], {})
        values = {}
        for entry in settings:
            name = entry["name"]
            value = profile.get(name)
            if value is None:
                value = default_value(definitions[name], enum_keys)
            elif isinstance(value, list) and entry["per_variant"]:
                variant = _variant_of(printer)
                listed = profile.get("print_extruder_variant", [])
                if variant not in listed:
                    raise TableError(f"process {item['name']}: its printer's extruder variant {variant!r} is not one "
                                     f"of its print_extruder_variant {listed!r}")
                value = value[listed.index(variant)]
            elif isinstance(value, list):
                value = value[0] if value else ""       # Orca reads the first value of a list it holds once
            values[name] = str(value)
        process_values[item["name"]] = values
    for entry in settings:
        if entry["kind"] == "text":
            longest = max((len(values[entry["name"]]) for values in process_values.values()), default=0)
            entry["max_length"] = max(1, longest)

    catalog = {
        "printers": [{"name": name, "printable_area": _corners(p.get("printable_area"), name),
                      "printable_height": _plain(float(p.get("printable_height", 0)))}
                     for name, p in printers.items()],
        "filaments": [{"name": e["name"], "printers": list(e.get("compatible_printers", []))}
                      for e in index.get("filaments", [])],
        "processes": [{"name": e["name"], "printers": list(e.get("compatible_printers", []))}
                      for e in index.get("processes", [])],
    }
    return {"format": FORMAT, "orca_version": index.get("orca_version"), "settings": settings,
            "process_values": process_values, "catalog": catalog}


def dumps(table):
    return json.dumps(table, indent=1, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=str(SOURCE_DIR), help="Orca's source for the pinned version")
    parser.add_argument("--catalog", default=str(CATALOG_DIR))
    parser.add_argument("--classification", default=str(CLASSIFICATION))
    parser.add_argument("--out", default=str(TABLE))
    parser.add_argument("--check", action="store_true", help="compare with --out instead of writing it")
    args = parser.parse_args(argv)
    try:
        text = dumps(build_table(args.source, args.catalog, args.classification))
    except TableError as exc:
        print(f"make-settings-table: {exc}", file=sys.stderr)
        return 1
    out = Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != text:
            print(f"make-settings-table: {out} differs from what the generator makes from {args.source}; "
                  f"run scripts/make_settings_table.py and review the diff", file=sys.stderr)
            return 1
        print(f"make-settings-table: {out} is what the generator makes")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"make-settings-table: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
