"""A group's configuration: `GET` and `PUT /api/configuration` (README-details.md, "The
configuration"; contracts/configuration.md).

One JSON document for each group in the state bucket, at `config/<group id>.json`, read
whole and written whole. **The front server never gives the wizard a configuration it cannot
use:** a group with no document gets the built-in default (the front server's own copy,
`default_configuration.json`, the contract's example file byte for byte); a group whose
saved document breaks one of the six rules of the contract gets the default in its place,
the saved file is left untouched, and one `configuration_invalid` line names the group, the
first rule broken and the path of the field. The answer's `revision` is the state bucket's
marker of the saved document as it stands, invalid or not.

A write is conditional on `based_on` (the marker it started from, or null for none): the
document is written in one canonical form (`records.record_bytes`), so that a write
repeated after its first attempt was written, which then finds `based_on` stale, is
recognised by the saved bytes being the ones it would write, and answered `200`. Every
edit writes a `configuration_edited` line with the user's name and each field that changed,
its old and its new value. The front server checks no Orca name against the profile catalog
and no override against the table of settings: those are the slice service's checks.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .answers import json_body
from .buckets import BucketUnavailable, ConditionFailed, NotFound
from .context import context
from .errors import FrontError
from .identity import acts_for_group, current_group, signed_in
from .records import FORMATS, record_bytes

#: A saved document larger than this breaks rule 1 (the contract's *proposed* 256 KB).
MAX_CONFIGURATION_BYTES = 262_144
DEFAULT_NAME = "PenguinSlicer default"
DEFAULT_BYTES = (Path(__file__).with_name("default_configuration.json")).read_bytes()
#: Each object's required and optional fields (contracts/configuration.md, "Fields").
FIELDS = {
    "document": ({"format", "printer", "upload_units", "filaments"}, {"note"}),
    "filament": ({"name", "colour", "profiles"}, {"note"}),
    "profile": ({"name", "purpose", "printer", "filament", "process"}, {"overrides", "note"}),
}
MAX_FILAMENTS = MAX_PROFILES = 20
MAX_NAME_CHARS = 40
MAX_PURPOSE_CHARS = 120
MAX_NOTE_CHARS = 2_000
MAX_OVERRIDE_NAME_CHARS = 100
#: The most of a field's name, and of a wrong value, that a line or an answer shows.
MAX_SHOWN_KEY_CHARS = 200
MAX_SHOWN_VALUE_CHARS = 40
COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
UNITS = ("in", "mm")


def register(app):
    app.add_url_rule("/api/configuration", "configuration_read", read_configuration,
                     methods=["GET"])
    app.add_url_rule("/api/configuration", "configuration_write", write_configuration,
                     methods=["PUT"])


def _name(group):
    return f"config/{group}.json"


@acts_for_group
def read_configuration():
    identity = signed_in()
    group = current_group(identity)
    ctx = context()
    try:
        with ctx["state_bucket"].open(_name(group)) as stored:
            revision = stored.marker
            # A document too large is not read at all.
            document, broken = (None, TOO_LARGE) if stored.size > MAX_CONFIGURATION_BYTES \
                else parse(stored.read())
    except NotFound:
        return _default(None)
    except BucketUnavailable as exc:
        raise FrontError("front.state_bucket_unreachable", f"reading {_name(group)}: {exc}")
    if broken is not None:
        ctx["log"].write("configuration_invalid", group=group, user_key=identity.user_id,
                         rule=broken.rule, path=broken.path, why=broken.why,
                         revision=revision)
        return _default(revision)
    return {"configuration": document, "source": "group",
            "name": identity.group_name(group), "revision": revision}


def _default(revision):
    return {"configuration": json.loads(DEFAULT_BYTES), "source": "default",
            "name": DEFAULT_NAME, "revision": revision}


@acts_for_group
def write_configuration():
    identity = signed_in()
    group = current_group(identity)
    body = json_body()
    if not isinstance(body, dict) or "configuration" not in body or "based_on" not in body:
        raise FrontError("front.bad_request",
                         "PUT /api/configuration takes an object with based_on and "
                         "configuration")
    based_on = body["based_on"]
    if based_on is not None and not (isinstance(based_on, str) and based_on):
        raise FrontError("front.bad_request", "based_on is neither a revision nor null")
    document = body["configuration"]
    if isinstance(document, dict):
        # The rules are checked on the document as sent, its own format number included;
        # what is written is its canonical form, which differs from it in no field.
        broken = parse(json.dumps(document).encode())[1]
        data = record_bytes("configuration", document)
    else:
        data, broken = None, NOT_AN_OBJECT
    if broken is not None:
        raise FrontError("front.configuration_invalid",
                         f"rule {broken.rule}, at {broken.path or 'the document'}: "
                         f"{broken.why}",
                         message=f"The configuration was not saved, because {broken.why}.")
    ctx = context()
    bucket, name = ctx["state_bucket"], _name(group)
    try:
        try:
            old = _loads(bucket.get(name)[0])
        except NotFound:
            old = None
        try:
            if based_on is None:
                revision = bucket.put(name, data, if_absent=True)
            else:
                revision = bucket.put(name, data, if_marker=based_on)
        except ConditionFailed:
            revision = _repeated(bucket, name, data)
        else:
            ctx["log"].write("configuration_edited", group=group, user_key=identity.user_id,
                             user_name=identity.user_name, revision=revision,
                             changes=changes(old, document))
    except BucketUnavailable as exc:
        raise FrontError("front.state_bucket_unreachable", f"writing {name}: {exc}")
    return {"revision": revision, "source": "group", "name": identity.group_name(group)}


def _repeated(bucket, name, data):
    """The saved document's marker when it is the one this write would make (a repeat whose
    first attempt was written); otherwise `front.configuration_changed`."""
    try:
        saved, marker = bucket.get(name)
    except NotFound:
        saved, marker = None, None
    if saved != data:
        raise FrontError("front.configuration_changed",
                         f"{name} is no longer the revision the write was based on")
    return marker


# What changed.

def _leaves(document):
    """Each leaf of `document` by its path (an empty list or object is a leaf). Walked with a
    list of its own rather than by calls, so that an old document nested deeper than Python's
    limit of calls, which its reader still reads, is walked too."""
    into, waiting = {}, [("", document)]
    while waiting:
        path, value = waiting.pop()
        if isinstance(value, dict) and value:
            waiting.extend((f"{path}.{key}" if path else key, item)
                           for key, item in value.items())
        elif isinstance(value, list) and value:
            waiting.extend((f"{path}[{index}]", item) for index, item in enumerate(value))
        else:
            into[path] = value
    return into


def changes(old, new):
    """Each field that differs between two documents: its path, old value and new value,
    None standing for a field that is not there. `old` that is not an object (none, not JSON,
    or another value) counts as empty."""
    before = _leaves(old) if isinstance(old, dict) else {}
    after = _leaves(new)
    return [{"path": path, "old": before.get(path), "new": after.get(path)}
            for path in sorted(set(before) | set(after))
            if before.get(path, _GONE) != after.get(path, _GONE)]


_GONE = object()


# The six rules (contracts/configuration.md, "When a document is invalid").

@dataclass(frozen=True)
class Broken:
    """A rule a document breaks: its number, the path of the field, and why, in words a
    person writing a document by hand understands."""

    rule: int
    path: str
    why: str


TOO_LARGE = Broken(1, "", f"it is larger than {MAX_CONFIGURATION_BYTES // 1024} KB")
NOT_AN_OBJECT = Broken(1, "", "it is not a JSON object")


def parse(raw):
    """The document the bytes `raw` hold and None, or None and the first rule it breaks: the
    lowest rule broken, and among the mistakes of that rule the first the checks meet. The
    checks run in a fixed order of fields, not in the document's order: in each object the
    fields missing (by name) before the fields not listed (in the document's order); then the
    document's `printer`, `upload_units`, `note` and `filaments`; each filament's `name`,
    `colour`, `note` and `profiles`; each profile's `name`, `purpose`, `printer`, `filament`,
    `process`, `note` and `overrides`; filaments and profiles in their lists' order."""
    if len(raw) > MAX_CONFIGURATION_BYTES:
        return None, TOO_LARGE
    document = _loads(raw)
    if document is _NOT_JSON:
        return None, Broken(1, "", "it is not JSON")
    if not isinstance(document, dict):
        return None, NOT_AN_OBJECT
    found = []
    _check_document(document, found.append)
    if found:
        return None, min(found, key=lambda broken: broken.rule)
    return document, None


_NOT_JSON = object()


def _loads(raw):
    """The value the bytes `raw` hold, or `_NOT_JSON`: bytes that are not JSON, and JSON
    nested deeper than Python's reader goes (it raises `RecursionError`, not `ValueError`),
    count alike as rule 1's "not JSON"."""
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        return _NOT_JSON


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _key(key):
    """A field's name as a path, a line and an answer show it: cut to `MAX_SHOWN_KEY_CHARS`,
    since a name the front server does not know may be of any length."""
    return key if len(key) <= MAX_SHOWN_KEY_CHARS else key[:MAX_SHOWN_KEY_CHARS] + "…"


def _shown(value):
    """A value of the wrong form as a sentence shows it: a list or an object by its kind, any
    other value as JSON cut to `MAX_SHOWN_VALUE_CHARS`."""
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    text = json.dumps(value)
    return text if len(text) <= MAX_SHOWN_VALUE_CHARS else text[:MAX_SHOWN_VALUE_CHARS] + "…"


def _fields(value, kind, path, report):
    required, optional = FIELDS[kind]
    at = (lambda key: f"{path}.{_key(key)}") if path else _key
    for key in sorted(required - set(value)):
        report(Broken(3, at(key), f"the field {at(key)} is missing"))
    for key in value:
        if key not in required | optional:
            report(Broken(3, at(key), f"the field {at(key)} is not one the configuration "
                                      "has"))


def _text(value, path, low, high, report, what="the field"):
    """Report rule 4 unless `value` is a string of `low` to `high` characters."""
    if not isinstance(value, str):
        report(Broken(4, path, f"{what} {path} is not text"))
    elif not low <= len(value) <= high:
        report(Broken(4, path, f"{what} {path} is not {low} to {high} characters long"))


def _note(value, path, report):
    if "note" in value:
        _text(value["note"], f"{path}.note" if path else "note", 0, MAX_NOTE_CHARS, report)


def _check_document(document, report):
    if "format" not in document:
        report(Broken(2, "format", "the field format is missing"))
    elif not _whole(document["format"]) or \
            not 1 <= document["format"] <= FORMATS["configuration"]:
        report(Broken(2, "format", f"format {_shown(document['format'])} is not a "
                                   "format this server reads"))
    _fields(document, "document", "", report)
    printer = document.get("printer")
    if "printer" in document and not isinstance(printer, str):
        report(Broken(4, "printer", "the field printer is not text"))
    if "upload_units" in document and document["upload_units"] not in UNITS:
        report(Broken(4, "upload_units", 'upload_units is neither "in" nor "mm"'))
    _note(document, "", report)
    if "filaments" in document:
        filaments = document["filaments"]
        if not isinstance(filaments, list) or not 1 <= len(filaments) <= MAX_FILAMENTS:
            report(Broken(4, "filaments", f"filaments is not a list of 1 to {MAX_FILAMENTS} "
                                          "filaments"))
        else:
            names = set()
            for index, filament in enumerate(filaments):
                _check_filament(filament, f"filaments[{index}]", names,
                                printer if isinstance(printer, str) else None, report)


def _unique_name(name, path, names, which, report):
    """Report rule 4 unless `name` is text of 1 to 40 characters not among `names`."""
    _text(name, path, 1, MAX_NAME_CHARS, report)
    if isinstance(name, str):
        if name in names:
            report(Broken(4, path, f"{which} are named {json.dumps(name)}"))
        names.add(name)


def _check_filament(filament, path, names, printer, report):
    if not isinstance(filament, dict):
        report(Broken(4, path, f"{path} is not an object"))
        return
    _fields(filament, "filament", path, report)
    if "name" in filament:
        _unique_name(filament["name"], f"{path}.name", names, "two filaments", report)
    if "colour" in filament and not (isinstance(filament["colour"], str)
                                     and COLOUR.fullmatch(filament["colour"])):
        report(Broken(4, f"{path}.colour", f"{path}.colour is not # and six hexadecimal "
                                           "digits"))
    _note(filament, path, report)
    if "profiles" in filament:
        profiles = filament["profiles"]
        if not isinstance(profiles, list) or not 1 <= len(profiles) <= MAX_PROFILES:
            report(Broken(4, f"{path}.profiles", f"{path}.profiles is not a list of 1 to "
                                                 f"{MAX_PROFILES} profiles"))
        else:
            profile_names = set()
            for index, profile in enumerate(profiles):
                _check_profile(profile, f"{path}.profiles[{index}]", profile_names, printer,
                               report)


def _check_profile(profile, path, names, printer, report):
    if not isinstance(profile, dict):
        report(Broken(4, path, f"{path} is not an object"))
        return
    _fields(profile, "profile", path, report)
    if "name" in profile:
        _unique_name(profile["name"], f"{path}.name", names, "two profiles of one filament",
                     report)
    if "purpose" in profile:
        _text(profile["purpose"], f"{path}.purpose", 1, MAX_PURPOSE_CHARS, report)
    for key in ("printer", "filament", "process"):
        if key in profile and not isinstance(profile[key], str):
            report(Broken(4, f"{path}.{key}", f"the field {path}.{key} is not text"))
    if isinstance(profile.get("printer"), str) and printer is not None \
            and profile["printer"] != printer:
        report(Broken(5, f"{path}.printer", f"{path}.printer is not the document's printer"))
    _note(profile, path, report)
    if "overrides" in profile:
        overrides = profile["overrides"]
        if not isinstance(overrides, dict):
            report(Broken(4, f"{path}.overrides", f"{path}.overrides is not an object"))
            return
        for key, value in overrides.items():
            at = f"{path}.overrides.{_key(key)}"
            if not 1 <= len(key) <= MAX_OVERRIDE_NAME_CHARS:
                report(Broken(6, at, f"an override's name in {path}.overrides is not 1 to "
                                     f"{MAX_OVERRIDE_NAME_CHARS} characters long"))
            elif not isinstance(value, str):
                report(Broken(6, at, f"the override {at} is not written as text"))
