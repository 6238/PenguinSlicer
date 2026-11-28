"""The table of settings (contracts/settings-table.md) and the check of a plate
configuration's `overrides` against it.

settings/table.json is generated from the pinned Orca's source by
scripts/make_settings_table.py and checked in; settings/classification.json says, for every
process setting of that Orca, whether it is a parameter (in the table), programmatic or not
offered, each of the last two with its reason. What the table holds is exactly what a plate
configuration may set: each override is Orca's own name with a string value as Orca writes it,
checked against its entry before Orca runs. Anything else refuses the plate configuration with
slice.bad_overrides, whose sentence and detail name the setting and say why.
"""
import functools
import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path

PKG = Path(__file__).resolve().parent
TABLE_PATH = PKG / "settings" / "table.json"
CLASSIFICATION_PATH = PKG / "settings" / "classification.json"
PROFILE_DIR = PKG / "profiles"

SHOWN_CHARS = 120            # a value a caller sent, as a sentence or a detail shows it, at most
DETAIL_PROBLEMS = 20         # problems listed in the detail, at most
MAX_NUMBER_CHARS = 40        # a number written longer than this is no number Orca writes
INT_RANGE = (-2 ** 31, 2 ** 31 - 1)       # Orca holds a whole-number setting in a C++ int

UNREADABLE_MESSAGE = "The slicer could not read its table of settings."
NOT_AN_OBJECT_MESSAGE = "The print settings could not be read."
UNKNOWN_MESSAGE = "The setting {name} is not a print setting the slicer knows."
REFUSED_MESSAGE = "The setting {name} cannot be changed: {reason}."
OTHER_PROFILE_MESSAGE = "The setting {name} belongs to the filament or printer profile, which a plate cannot change."
NOT_TEXT_MESSAGE = "{setting} must be given as text, as Orca writes it, not {value}."
CHOICE_MESSAGE = "{setting} cannot be {value}: choose one of the values Orca offers for it."
FORM_MESSAGE = "{setting} must be {form}, not {value}."
BELOW_MESSAGE = "{setting} must be at least {bound}, not {value}."
ABOVE_MESSAGE = "{setting} must be at most {bound}, not {value}."
TOO_LONG_MESSAGE = "{setting} can be at most {length} characters long."
CONTROL_MESSAGE = "{setting} cannot hold a line break or other control character."

FORM_WORDS = {"integer": "a whole number", "decimal": "a number", "percent": "a percentage such as 40%",
              "decimal_or_percent": "a number or a percentage"}
_DECIMAL = r"-?[0-9]+(?:\.[0-9]+)?"          # ASCII digits only: `\d` takes any script's digits
FORMS = {"integer": re.compile(r"-?[0-9]+"), "decimal": re.compile(_DECIMAL),
         "percent": re.compile(_DECIMAL + "%"), "decimal_or_percent": re.compile(_DECIMAL + "%?")}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class TableUnreadable(Exception):
    """The slice service's own table of settings is missing or not a table."""

    error_code = "slice.profile_unreadable"

    def __init__(self, details):
        super().__init__(UNREADABLE_MESSAGE)
        self.message = UNREADABLE_MESSAGE
        self.details = details


class OverrideError(Exception):
    """Overrides the slice service will not use: `message` names the first setting and says
    why, `details` lists every problem for the log."""

    error_code = "slice.bad_overrides"

    def __init__(self, message, details=""):
        super().__init__(message)
        self.message = message
        self.details = details


@dataclass(frozen=True)
class Table:
    """The table as served (`raw`, its bytes), read (`data`) and by setting (`entries`)."""
    raw: bytes
    data: dict
    entries: dict

    @functools.cached_property
    def gzipped(self):
        return gzip.compress(self.raw, mtime=0)


@functools.lru_cache(maxsize=1)
def load():
    """The checked-in table, read once per process: it changes only with the Orca version."""
    try:
        raw = TABLE_PATH.read_bytes()
        data = json.loads(raw)
        entries = {entry["name"]: entry for entry in data["settings"]}
        data["process_values"], data["catalog"]       # noqa: B018 - the shape a table has
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TableUnreadable(f"{TABLE_PATH}: {type(exc).__name__}: {exc}"[:500]) from None
    return Table(raw, data, entries)


@functools.lru_cache(maxsize=1)
def _classification():
    try:
        return json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@functools.lru_cache(maxsize=1)
def _other_profiles_settings():
    """The names of the default set's filament and printer settings: what a plate cannot change."""
    names = set()
    for kind in ("filament", "printer"):
        try:
            names |= set(json.loads((PROFILE_DIR / f"{kind}.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return names


def _shown(value):
    """A value a caller sent, for a sentence or a detail: its repr, cut to SHOWN_CHARS."""
    try:
        text = repr(value)
    except RecursionError:
        return "a value nested too deeply"
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "..."


def _setting(entry):
    """A setting as a sentence names it: Orca's label, with its page and group."""
    return f"{entry['label']} ({entry['section']}, {entry['group']})"


def _bound(entry, value):
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text + "%" if entry["number_form"] == "percent" else text


def _problem(name, value, table):
    """(sentence, detail) of why `name` = `value` is refused, or None when it is accepted."""
    entry = table.entries.get(name)
    plain = isinstance(name, str) and len(name) <= SHOWN_CHARS and name.isprintable()
    shown_name = name if plain else _shown(name)
    if entry is None:
        classification = _classification()
        for group in ("programmatic", "not_offered"):
            reason = classification.get(group, {}).get(name)
            if reason:
                return REFUSED_MESSAGE.format(name=name, reason=reason), f"override {name!r} is {group}: {reason}"
        if name in _other_profiles_settings():
            return OTHER_PROFILE_MESSAGE.format(name=name), f"override {name!r} is a filament or printer setting"
        return UNKNOWN_MESSAGE.format(name=shown_name), f"override {_shown(name)} is not in the table of settings"
    setting, shown = _setting(entry), _shown(value)
    if not isinstance(value, str):
        return NOT_TEXT_MESSAGE.format(setting=setting, value=shown), f"override {name!r} is {shown}, not a string"
    kind = entry["kind"]
    if kind == "choice":
        allowed = [choice["value"] for choice in entry["choices"]]
        if value not in allowed:
            return CHOICE_MESSAGE.format(setting=setting, value=shown), \
                f"override {name!r} is {shown}, not one of {allowed}"[:600]
    elif kind == "text":
        if len(value) > entry["max_length"]:
            return TOO_LONG_MESSAGE.format(setting=setting, length=entry["max_length"]), \
                f"override {name!r} has {len(value)} characters, max_length {entry['max_length']}"
        if _CONTROL.search(value):
            return CONTROL_MESSAGE.format(setting=setting), f"override {name!r} holds a control character"
    else:
        form = entry["number_form"]
        figure = value[:-1] if value.endswith("%") else value
        if len(value) > MAX_NUMBER_CHARS or not FORMS[form].fullmatch(value) or (
                form == "integer" and not INT_RANGE[0] <= int(value) <= INT_RANGE[1]):
            return FORM_MESSAGE.format(setting=setting, form=FORM_WORDS[form], value=shown), \
                f"override {name!r} is {shown}, not of the form {form}"
        number = float(figure)
        if "min" in entry and number < entry["min"]:
            return BELOW_MESSAGE.format(setting=setting, bound=_bound(entry, entry["min"]), value=value), \
                f"override {name!r} is {value}, below min {entry['min']}"
        if "max" in entry and number > entry["max"]:
            return ABOVE_MESSAGE.format(setting=setting, bound=_bound(entry, entry["max"]), value=value), \
                f"override {name!r} is {value}, above max {entry['max']}"
    return None


def validate_overrides(raw):
    """A plate configuration's `overrides`, checked against the table: {name: value}, each
    exactly as sent. Raises OverrideError naming the first problem, every one in its detail."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OverrideError(NOT_AN_OBJECT_MESSAGE, f"overrides is not an object: {_shown(raw)}")
    table = load()
    problems = [p for p in (_problem(name, value, table) for name, value in raw.items()) if p]
    if problems:
        detail = "; ".join(d for _s, d in problems[:DETAIL_PROBLEMS])
        if len(problems) > DETAIL_PROBLEMS:
            detail += f"; and {len(problems) - DETAIL_PROBLEMS} more"
        raise OverrideError(problems[0][0], detail)
    return dict(raw)


def per_variant(name):
    """Whether Orca keeps one value of the setting for each extruder variant."""
    entry = load().entries.get(name)
    return bool(entry and entry.get("per_variant"))
