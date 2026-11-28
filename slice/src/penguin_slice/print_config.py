"""The profile choice of a plate configuration, read against the profile catalog, and its
overrides written over the process profile.

A plate configuration names its printer, filament and process by Orca's own profile names
(profiles/catalog/index.json lists them). A plate configuration with no printer prints with the
default set in profiles/. A printer name the catalog does not know fails closed: no
fallback. A filament or process the catalog does not know, or that does not fit the
printer, is refused. Its overrides are checked against the table of settings
(settings_table.validate_overrides) and replace values of the process profile only.
"""
import functools
import json
from pathlib import Path

from .settings_table import OverrideError, per_variant, validate_overrides  # noqa: F401 - the plate's checks
from .slicer import DEFAULT_PROFILES, PROFILE_DIR, SliceProfiles

PKG = Path(__file__).resolve().parent      # the penguin_slice package directory
CATALOG_DIR = PKG / 'profiles' / 'catalog'

UNKNOWN_PRINTER_MESSAGE = "The printer '{name}' is not one the slicer knows."
CHOOSE_PROFILES_MESSAGE = "Choose a filament and print settings from the list."

SHOWN_CHARS = 120     # a value a caller sent, as a sentence or a detail shows it, at most


def _shown(value, quoted=True):
    """A value a caller sent, for a sentence or a detail: its repr (its text when not
    `quoted`), cut to SHOWN_CHARS with "...", whatever its size or depth."""
    try:
        text = repr(value) if quoted or not isinstance(value, str) else value
    except RecursionError:
        return "a value nested too deeply"
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "..."


# Catalog kind -> index.json list name.
_LISTS = {'printer': 'printers', 'filament': 'filaments', 'process': 'processes'}


class Catalog:
    """profiles/catalog/index.json, by kind and name."""

    def __init__(self, directory, index):
        self.directory = Path(directory)
        self.orca_version = index.get('orca_version')
        self._entries = {kind: {e['name']: e for e in index.get(list_name, [])}
                         for kind, list_name in _LISTS.items()}

    @classmethod
    def load(cls, directory=CATALOG_DIR):
        with open(Path(directory) / 'index.json', encoding='utf-8') as fh:
            return cls(directory, json.load(fh))

    def printer_names(self):
        return list(self._entries['printer'])

    def has_printer(self, name):
        return isinstance(name, str) and name in self._entries['printer']

    def profile_path(self, kind, name):
        return self.directory / self._entries[kind][name]['file']

    def compatible(self, kind, name, printer):
        entry = self._entries[kind].get(name) if isinstance(name, str) else None
        return entry is not None and printer in entry.get('compatible_printers', [])


@functools.lru_cache(maxsize=1)
def load_catalog():
    """The catalog, read once per process: it is committed and changes only with a release."""
    return Catalog.load()


class ProfileError(ValueError):
    """A printer, filament or process the slice service will not slice with.

    `message` is one sentence for the user; `details` names the choice for the log;
    `error_code` is the error report's code. `remedy`, when set, replaces the code's remedy
    and `no_action` drops its action (service.check_part sets both for a part being added)."""

    def __init__(self, message, details="", error_code="slice.profiles_not_offered"):
        super().__init__(message)
        self.message = message
        self.details = details
        self.error_code = error_code
        self.remedy = None
        self.no_action = False


def _profile_name(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)['name']


def default_names():
    """(printer, filament, process): the names of the three files in profiles/."""
    return tuple(_profile_name(PROFILE_DIR / f'{kind}.json') for kind in ('printer', 'filament', 'process'))


def choose_profiles(printer, filament, process, catalog=None):
    """The three files for a slice. `printer` None is the default set, whose filament and
    process may be left out (None) or named. Raises ProfileError otherwise."""
    not_offered = f"filament {_shown(filament)} or process {_shown(process)} is not offered"
    if printer is None:
        _printer, default_filament, default_process = default_names()
        if filament not in (None, default_filament) or process not in (None, default_process):
            raise ProfileError(CHOOSE_PROFILES_MESSAGE, not_offered + " with the default set")
        return DEFAULT_PROFILES
    catalog = catalog or load_catalog()
    if not catalog.has_printer(printer):
        raise ProfileError(UNKNOWN_PRINTER_MESSAGE.format(name=_shown(printer, quoted=False)), f"printer {_shown(printer)} is not in the catalog",
                           error_code="slice.unknown_printer")
    if not (catalog.compatible('filament', filament, printer) and catalog.compatible('process', process, printer)):
        raise ProfileError(CHOOSE_PROFILES_MESSAGE, f"{not_offered} for printer {_shown(printer)}")
    return SliceProfiles(catalog.profile_path('printer', printer), catalog.profile_path('filament', filament),
                         catalog.profile_path('process', process))


def printer_profile(profiles):
    """The chosen printer's flattened profile, for plate.plate_from_printer."""
    with open(profiles.printer, encoding='utf-8') as fh:
        return json.load(fh)


def supports_on(profiles, overrides):
    """Whether the plate is sliced with supports: `enable_support` of the overrides when they
    set it, else the chosen process profile's own value."""
    if 'enable_support' in overrides:
        return overrides['enable_support'] == '1'
    with open(profiles.process, encoding='utf-8') as fh:
        return str(json.load(fh).get('enable_support', '0')) == '1'


def write_process_with_overrides(process_path, overrides, out_path):
    """The process profile with `overrides` (checked by validate_overrides) written over it,
    to `out_path`. A setting Orca keeps for each extruder variant takes the one value for
    every variant the profile lists."""
    with open(process_path, encoding='utf-8') as fh:
        process = json.load(fh)
    variants = max(1, len(process.get('print_extruder_variant') or []))
    for name, value in overrides.items():
        process[name] = [value] * variants if per_variant(name) else value
    out_path = Path(out_path)
    out_path.write_text(json.dumps(process, indent=4, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    return out_path
