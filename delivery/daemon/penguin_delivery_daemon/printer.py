"""The only module that touches bambulabs_api.

Two jobs. `map_status` turns the printer's own report document into the six-word vocabulary
the relay and the caller use, plus the printer's stage -- a pure function of a dictionary,
so a captured fixture pins it. `PrinterLink` is the thin shim over the library: connect,
read, upload, verify, delete, start.

The library is imported lazily, inside connect(), so this module imports (and its tests
run) on a machine that does not have it -- which is what keeps `make test` honest when
bambulabs_api is absent.

**The library's own log.** bambulabs_api logs through the `bambulabs_api` logger, and some
of its lines look like failures when nothing failed (the H2S's `426 Failure reading
network stream` after an upload that arrived whole). PrinterLink takes that logger over:
nothing from it reaches the console as it is. Lines logged during an upload are kept as the
upload's evidence; warnings and errors at other times are passed to the daemon's log as one
plain line beginning "printer library said:", and everything below a warning is dropped.
"""

import logging
import os
import re
import socket
import threading
import time

# The only state names that leave this module.
IDLE = 'idle'
RUNNING = 'running'
PAUSED = 'paused'
FINISHED = 'finished'
ERROR = 'error'
UNREACHABLE = 'unreachable'
#: The printer's main state is one this version does not know: nobody can tell whether a
#: print is going on. A new send is refused; a followed print shows as stale.
UNRECOGNISED_STATE = 'unrecognised'

# -- What every value the printer reports means for a print ------------------------------
#
# The one table. Every printer state (`gcode_state`), stage code (`stg_cur`) and error field
# (`print_error`, the severity of an `hms` entry) the daemon reads is in it, in one of six
# classes. The guide prints it ("What the printer's report means"), and a test checks that
# the guide and this table agree.
#
# - going: the print is under way;
# - waiting: the print is under way but the printer is waiting for a person (a pause, an
#   error code set while the print is paused or running, a door open, filament run out, a
#   serious HMS entry). NEVER an end: the print goes on once someone deals with it;
# - ended_well: the print finished;
# - ended_badly: the printer's own state says the print ended without finishing;
# - idle: no print;
# - unrecognised: the main state is the library's placeholder for one it could not read.
#
# The main state decides whether a print is going on; the stage code only describes what a
# going print is doing (see classify). A stage code not in the table, under a going main
# state, is "going, unrecognised stage"; a main state not in the table is unrecognised as a
# whole. Either way the raw value is kept in the snapshot (`unrecognised`), and it never
# ends a print.

GOING = 'going'
WAITING = 'waiting'
ENDED_WELL = 'ended_well'
ENDED_BADLY = 'ended_badly'
NO_PRINT = 'idle'
UNRECOGNISED = 'unrecognised'

#: How each class reads in the snapshot's `state`, the seven-word vocabulary the relay uses
#: (with `unreachable`).
CLASS_STATE = {GOING: RUNNING, WAITING: PAUSED, ENDED_WELL: FINISHED, ENDED_BADLY: ERROR,
               NO_PRINT: IDLE, UNRECOGNISED: UNRECOGNISED_STATE}

_RESUME = "then resume the print on the printer's screen."

#: (field, value) -> (class, name, label, what to do at the printer). The `stg_cur`
#: numbers and the library's names for them (in the comments) are bambulabs_api's
#: GcodeState and PrintStatus; the upstream check (`make test-upstream`) fails when the
#: library's tables stop agreeing with this one. PROVISIONAL where it says what the H2S
#: does while it waits for a person: no real pause has been recorded yet.
PRINTER_VALUES = {
    # The printer's state, which decides whether a print is going on. PREPARE is a real
    # print in its first seconds, so it is going. IDLE is no print whatever the stage says.
    ('gcode_state', 'IDLE'): (NO_PRINT, 'idle', 'Not printing', None),
    ('gcode_state', 'PREPARE'): (GOING, 'preparing', 'Preparing the print', None),
    ('gcode_state', 'RUNNING'): (GOING, 'printing', 'Printing', None),
    ('gcode_state', 'PAUSE'): (WAITING, 'paused', 'Paused at the printer',
                               "Resume the print on the printer's screen, or stop it there."),
    ('gcode_state', 'FINISH'): (ENDED_WELL, 'finished', 'Finished', None),
    ('gcode_state', 'FAILED'): (ENDED_BADLY, 'failed', 'The print failed or was stopped',
                                None),
    # The library's own placeholder for a state it could not read: never an end, never free.
    ('gcode_state', 'UNKNOWN'): (UNRECOGNISED, 'unknown', 'State not recognised', None),
    # The printer's stage: what a going print is doing. Read only under a going state.
    ('stg_cur', 0): (GOING, 'printing', 'Printing', None),                       # PRINTING
    ('stg_cur', 1): (GOING, 'leveling_bed', 'Levelling the bed', None),          # AUTO_BED_LEVELING
    ('stg_cur', 2): (GOING, 'heating_bed', 'Heating the bed', None),             # HEATBED_PREHEATING
    ('stg_cur', 3): (GOING, 'sweeping', 'Sweeping the axes', None),              # SWEEPING_XY_MECH_MODE
    ('stg_cur', 4): (GOING, 'changing_filament', 'Changing filament', None),     # CHANGING_FILAMENT
    ('stg_cur', 5): (WAITING, 'paused', 'Paused',                                # M400_PAUSE
                     f'Check the print, {_RESUME}'),
    ('stg_cur', 6): (WAITING, 'paused_filament_runout', 'Paused: the filament ran out',
                     f'Load new filament, {_RESUME}'),                           # PAUSED_FILAMENT_RUNOUT
    ('stg_cur', 7): (GOING, 'heating_nozzle', 'Heating the nozzle', None),       # HEATING_HOTEND
    ('stg_cur', 8): (GOING, 'calibrating_extrusion', 'Calibrating extrusion', None),  # CALIBRATING_EXTRUSION
    ('stg_cur', 9): (GOING, 'scanning_bed', 'Scanning the bed', None),           # SCANNING_BED_SURFACE
    ('stg_cur', 10): (GOING, 'inspecting_first_layer', 'Inspecting the first layer', None),  # INSPECTING_FIRST_LAYER
    ('stg_cur', 11): (GOING, 'identifying_plate', 'Checking the build plate', None),  # IDENTIFYING_BUILD_PLATE_TYPE
    ('stg_cur', 12): (GOING, 'calibrating_lidar', 'Calibrating the camera', None),  # CALIBRATING_MICRO_LIDAR
    ('stg_cur', 13): (GOING, 'homing', 'Homing', None),                          # HOMING_TOOLHEAD
    ('stg_cur', 14): (GOING, 'cleaning_nozzle', 'Cleaning the nozzle', None),    # CLEANING_NOZZLE_TIP
    ('stg_cur', 15): (GOING, 'checking_temperature', 'Checking the nozzle temperature', None),  # CHECKING_EXTRUDER_TEMPERATURE
    ('stg_cur', 16): (WAITING, 'paused_by_user', 'Paused at the printer',        # PAUSED_USER
                      "Resume the print on the printer's screen, or stop it there."),
    ('stg_cur', 17): (WAITING, 'paused_cover_open', 'Paused: the front cover is open',
                      f'Close the front cover, {_RESUME}'),                      # PAUSED_FRONT_COVER_FALLING
    ('stg_cur', 18): (GOING, 'calibrating_lidar', 'Calibrating the camera', None),  # CALIBRATING_LIDAR
    ('stg_cur', 19): (GOING, 'calibrating_flow', 'Calibrating the flow', None),  # CALIBRATING_EXTRUSION_FLOW
    ('stg_cur', 20): (WAITING, 'paused_nozzle_temperature', 'Paused: nozzle temperature fault',
                      f'Check the nozzle heater, {_RESUME}'),                    # PAUSED_NOZZLE_TEMPERATURE_MALFUNCTION
    ('stg_cur', 21): (WAITING, 'paused_bed_temperature', 'Paused: bed temperature fault',
                      f'Check the heated bed, {_RESUME}'),                       # PAUSED_HEAT_BED_TEMPERATURE_MALFUNCTION
    ('stg_cur', 22): (GOING, 'unloading_filament', 'Unloading filament', None),  # FILAMENT_UNLOADING
    ('stg_cur', 23): (WAITING, 'paused_skipped_step', 'Paused: a motor skipped steps',
                      f'Check that nothing blocks the print head, {_RESUME}'),   # PAUSED_SKIPPED_STEP
    ('stg_cur', 24): (GOING, 'loading_filament', 'Loading filament', None),      # FILAMENT_LOADING
    ('stg_cur', 25): (GOING, 'calibrating_motor_noise', 'Calibrating motor noise', None),  # CALIBRATING_MOTOR_NOISE
    ('stg_cur', 26): (WAITING, 'paused_ams_lost', 'Paused: the AMS was lost',
                      f'Check the AMS connection, {_RESUME}'),                   # PAUSED_AMS_LOST
    ('stg_cur', 27): (WAITING, 'paused_fan', 'Paused: a fan is too slow',
                      f'Check the hotend fan, {_RESUME}'),                       # PAUSED_LOW_FAN_SPEED_HEAT_BREAK
    ('stg_cur', 28): (WAITING, 'paused_chamber_temperature', 'Paused: chamber temperature fault',
                      f'Check the chamber temperature, {_RESUME}'),              # PAUSED_CHAMBER_TEMPERATURE_CONTROL_ERROR
    ('stg_cur', 29): (GOING, 'cooling_chamber', 'Cooling the chamber', None),    # COOLING_CHAMBER
    ('stg_cur', 30): (WAITING, 'paused_by_gcode', 'Paused by the print file',
                      f'Do what the print file paused for, {_RESUME}'),          # PAUSED_USER_GCODE
    ('stg_cur', 31): (GOING, 'motor_noise_showoff', 'Testing the motors', None),  # MOTOR_NOISE_SHOWOFF
    ('stg_cur', 32): (WAITING, 'paused_nozzle_covered', 'Paused: filament is covering the nozzle',
                      f'Clear the filament from around the nozzle, {_RESUME}'),  # PAUSED_NOZZLE_FILAMENT_COVERED_DETECTED
    ('stg_cur', 33): (WAITING, 'paused_cutter', 'Paused: the filament cutter failed',
                      f'Check the filament cutter, {_RESUME}'),                  # PAUSED_CUTTER_ERROR
    ('stg_cur', 34): (WAITING, 'paused_first_layer', 'Paused: a first layer problem',
                      f'Look at the first layer, {_RESUME}'),                    # PAUSED_FIRST_LAYER_ERROR
    ('stg_cur', 35): (WAITING, 'paused_nozzle_clog', 'Paused: the nozzle may be clogged',
                      f'Check the nozzle for a clog, {_RESUME}'),                # PAUSED_NOZZLE_CLOG
    ('stg_cur', 255): (NO_PRINT, 'idle', 'Idle', None),                          # IDLE
    # The error fields. A code set while the print is paused or running is the printer
    # waiting for a person; with the printer idle or FAILED, it is how the print ended.
    ('print_error', 0): (GOING, 'none', 'No error', None),
    ('print_error', 'any other'): (WAITING, 'printer_error',
                                   'The printer reported a problem',
                                   f"Deal with what the printer's screen shows, {_RESUME}"),
    ('hms severity', 1): (WAITING, 'printer_error', 'The printer reported a fatal fault',
                          f"Deal with what the printer's screen shows, {_RESUME}"),
    ('hms severity', 2): (WAITING, 'printer_error', 'The printer reported a serious fault',
                          f"Deal with what the printer's screen shows, {_RESUME}"),
    ('hms severity', 3): (GOING, 'notice', 'The printer reported a notice', None),
    ('hms severity', 4): (GOING, 'notice', 'The printer reported some information', None),
}

#: Views of the table, by field.
GCODE_STATES = {value: row for (field, value), row in PRINTER_VALUES.items()
                if field == 'gcode_state'}
GCODE_STATE_MAP = {value: CLASS_STATE[row[0]] for value, row in GCODE_STATES.items()}
STAGE_VALUES = {value: row for (field, value), row in PRINTER_VALUES.items()
                if field == 'stg_cur'}
STG_IDLE = 255
STG_PAUSED = frozenset(code for code, row in STAGE_VALUES.items() if row[0] == WAITING)
#: The printer's stage (`stg_cur`) as a stable name and words a student understands. A code
#: not listed becomes `stage_<n>`, "Busy (stage n)".
PRINTER_STAGES = {code: (row[1], row[2]) for code, row in STAGE_VALUES.items()}
#: The HMS severities that mean the printer waits for a person (1 fatal, 2 serious).
HMS_SEVERITY_STOPS = frozenset(value for (field, value), row in PRINTER_VALUES.items()
                               if field == 'hms severity' and row[0] == WAITING)
_HMS_KNOWN = frozenset(value for (field, value) in PRINTER_VALUES if field == 'hms severity')


def printer_stage(stage_code):
    """(name, label) for a `stg_cur` value; an unknown or missing one is named honestly."""
    if stage_code is None:
        return None, None
    if stage_code in PRINTER_STAGES:
        return PRINTER_STAGES[stage_code]
    return f'stage_{stage_code}', f'Busy (stage {stage_code})'


def values_table():
    """The table as the guide prints it: one Markdown row per value."""
    names = {GOING: 'going', WAITING: 'waiting for a person', ENDED_WELL: 'ended well',
             ENDED_BADLY: 'ended badly', NO_PRINT: 'no print',
             UNRECOGNISED: 'unrecognised as a whole'}
    rows = ['| Field | Value | Means | Name | What to do at the printer |',
            '|---|---|---|---|---|']
    for (field, value), (kind, name, _label, remedy) in PRINTER_VALUES.items():
        rows.append(f'| `{field}` | `{value}` | {names[kind]} | `{name}` | {remedy or ""} |')
    rows.append('| `gcode_state` | a value not listed | unrecognised as a whole (the raw '
                'value is kept in `unrecognised`) | | |')
    rows.append('| `gcode_state` | missing, `null` or empty | unrecognised as a whole, '
                'whatever else the document says: it says nothing about whether a print is '
                'going on (`unrecognised` says "no main state (gcode_state) reported yet") '
                '| | |')
    rows.append('| `stg_cur` | a value not listed | under a going state: going, '
                'unrecognised stage; under `IDLE`: no print (the raw value is kept in '
                '`unrecognised`) | | |')
    rows.append('| `hms` severity | a value not listed | changes nothing (the raw value is '
                'kept in `unrecognised`) | | |')
    return '\n'.join(rows)

# The compound extensions a sliced file can carry, longest first.
_EXTENSIONS = ('.gcode.3mf', '.3mf', '.gcode')

#: The plate inside the archive to print. The slice service slices one plate and Orca
#: numbers it 1 (Metadata/plate_1.gcode inside the sliced file). Named rather than written
#: into the start call, so the sliced-file contract can pin the two together once it is
#: written: the daemon never imports the slice service, so a test is the only place they
#: meet.
PLATE_NUMBER = 1

#: The three outcomes of PrinterLink.delete, each decided by the printer's answer to the
#: delete and never by a listing: REMOVED when it confirmed the delete; NOT_ON_PRINTER when
#: it answered that there is no such file (an upload that never reached it), so there was
#: nothing to remove; UNCONFIRMED for any other answer, or none.
REMOVED = 'removed'
NOT_ON_PRINTER = 'not_on_printer'
UNCONFIRMED = 'unconfirmed'

# The printer's answer that it has no such file: a 550 that says so. A 550 that says
# anything else (a refusal, "Delete operation failed") is not taken as proof of absence.
_NO_SUCH_FILE_RE = re.compile(
    r'^550\b.*\b(no such file|not found|does not exist|doesn\'t exist)', re.IGNORECASE)
# An FTP server's reply begins with its three-digit code.
_FTP_REPLY_RE = re.compile(r'^\d{3}')
# How the library's connect_and_run logs the error it swallows.
_LIBRARY_FAILURE = 'Failed to execute function: '

# A job id is 'j' + hex: the relay builds it as "j" + secrets.token_hex(4), and a leading
# zero can be dropped, so 7 or 8 hex digits -- the same rule the relay applies. Deliberately
# tight: a wider pattern would strip suffixes this daemon never wrote, turning a user's
# `part-jaded.gcode.3mf` into `part.gcode.3mf`.
_JOB_ID_RE = re.compile(r'^j[0-9a-f]{7,8}$')

# An HMS entry's severity lives in the high 16 bits of its `code` word: 1 fatal, 2 serious,
# 3 common, 4 info (OpenBambuAPI's hms.md, which is also how Bambu Studio colours the entry
# -- the pinned bambulabs_api exposes no HMS accessor at all, so there is no library constant to
# use). Fatal and serious make the printer wait for a person (PRINTER_VALUES); an info entry
# can sit in the list through a perfectly healthy job. PROVISIONAL with the rest of the
# table until a real status is recorded.

# SSDP: Bambu printers announce themselves to this group and port. Binding the port is not
# enough on Linux -- without joining the group the kernel drops every datagram.
DISCOVERY_PORT = 2021
DISCOVERY_GROUP = '239.255.255.250'


def format_hms(attr, code):
    """The printer's HMS error in the form the screen and the wiki use.

    attr and code are two 32-bit integers; each becomes two four-hex-digit groups."""
    attr, code = int(attr), int(code)
    return (f"HMS_{(attr >> 16) & 0xFFFF:04X}_{attr & 0xFFFF:04X}"
            f"_{(code >> 16) & 0xFFFF:04X}_{code & 0xFFFF:04X}")


def suffixed_name(filename, job_id):
    """`sample_part.gcode.3mf` + `j8f3a2c1` -> `sample_part-j8f3a2c1.gcode.3mf`.

    The job id is in the name the printer reports back, which is how the daemon tells its
    own job from the previous one and how a restarted daemon recognises a job already
    running. The wizard strips the suffix for display."""
    for ext in _EXTENSIONS:
        if filename.endswith(ext):
            return f"{filename[:-len(ext)]}-{job_id}{ext}"
    stem, ext = os.path.splitext(filename)
    return f"{stem}-{job_id}{ext}"


def strip_job_suffix(filename):
    """Undo suffixed_name for display. A name this daemon did not write is left alone.
    The H2S reports the name without its extension (`subtask_name`), and that form is
    undone too."""
    for ext in _EXTENSIONS + ('',):
        if filename.endswith(ext):
            stem = filename[:-len(ext)] if ext else filename
            head, dash, tail = stem.rpartition('-')
            if dash and _JOB_ID_RE.match(tail):
                return f"{head}{ext}"
            if ext:
                return filename
    return filename


def name_without_extension(remote_name):
    """`sample_part-j8f3a2c1.gcode.3mf` -> `sample_part-j8f3a2c1`: what the H2S reports
    as `subtask_name` for the file it is printing."""
    for ext in _EXTENSIONS:
        if remote_name.endswith(ext):
            return remote_name[:-len(ext)]
    return os.path.splitext(remote_name)[0]


def reports_file(snapshot, remote_name):
    """Does this snapshot say the printer has our uploaded file as its current print?

    The H2S names its print in `subtask_name` without the extension, and puts the G-code
    path inside the archive (`/data/Metadata/plate_1.gcode`) in `gcode_file`. map_status
    keeps the first as `job_name`. A printer that reports the whole name is accepted too.
    The job id is in the name, so the previous print can never be mistaken for ours."""
    names = {snapshot.get('job_name') or '', snapshot.get('file') or ''}
    return bool({remote_name, name_without_extension(remote_name)} & names)


#: Characters Windows forbids in a file name, and control characters. Replaced in every
#: name this daemon writes to disk or sends to the printer.
_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = frozenset({'CON', 'PRN', 'AUX', 'NUL', *(f'COM{n}' for n in range(1, 10)),
                               *(f'LPT{n}' for n in range(1, 10))})


def safe_file_name(name, fallback='sliced_part.gcode.3mf'):
    """A name that is a plain file name on Windows, macOS and Linux: no directory, no
    forbidden character, no reserved device name, no trailing dot or space, at most 120
    characters. The relay sends the name; the daemon never trusts it."""
    name = os.path.basename(str(name or '').replace('\\', '/'))
    name = _FORBIDDEN_RE.sub('_', name).strip().rstrip('. ')
    if not name or name.startswith('.'):
        name = fallback
    stem = name.split('.', 1)[0]
    if stem.upper() in _WINDOWS_RESERVED:
        name = f'_{name}'
    if len(name) > 120:
        for ext in _EXTENSIONS:
            if name.endswith(ext):
                name = name[:120 - len(ext)] + ext
                break
        else:
            name = name[:120]
    return name


def _as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _hms_severity(entry):
    """The severity number in the high 16 bits of an HMS entry's code word."""
    return ((_as_int(entry.get('code'), 0) or 0) >> 16) & 0xFFFF


def _worst_hms(entries):
    """The one entry to put on the status line.

    A printer lists its HMS entries in its own order, not in severity order, so a fatal
    fault can sit behind an informational one. A stopping entry outranks an entry that only
    reports something, and below that the lower severity number wins (1 fatal is worse than
    4 info). min() keeps the first of equals, which is the order the printer sent."""
    return min(entries, key=lambda entry: (_hms_severity(entry) not in HMS_SEVERITY_STOPS,
                                           _hms_severity(entry)))


def classify(report):
    """(class, waiting row or None, unrecognised values) for one status document, read by
    PRINTER_VALUES.

    The printer's main state (`gcode_state`) decides whether a print is going on; the stage
    code (`stg_cur`) only describes what a going print is doing. In order:

    - a main state this version does not know (or the library's own UNKNOWN): unrecognised
      as a whole, whatever else the document says;
    - the printer's own end (FINISH, FAILED);
    - a main state that means no print (IDLE): no print whatever the stage code says, or,
      with an error code or a serious HMS entry set, how the last print ended;
    - a going main state (PREPARE, RUNNING, PAUSE): a stage that waits for a person, then an
      error code or a serious HMS entry (the printer waits for a person), then a pause, else
      the print is going. A stage code the table does not know is "going, unrecognised
      stage", its raw value kept;
    - no main state in the document at all: it says nothing about whether a print is going
      on, whatever its stage code, figures or file name say. Unrecognised as a whole, so it
      is never free (see "How a start is decided" in the guide)."""
    unrecognised = []
    raw_state = report.get('gcode_state')
    state_key = str(raw_state).upper() if raw_state not in (None, '') else None
    state_row = GCODE_STATES.get(state_key) if state_key else None
    if state_key and state_row is None:
        unrecognised.append(f'gcode_state {str(raw_state)[:40]!r}')
    raw_stage = report.get('stg_cur')
    stage_row = STAGE_VALUES.get(_as_int(raw_stage)) if raw_stage is not None else None
    if raw_stage is not None and stage_row is None:
        unrecognised.append(f'stg_cur {str(raw_stage)[:40]!r}')
    print_error = _as_int(report.get('print_error'), 0) or 0
    hms = report.get('hms')
    entries = [h for h in hms if isinstance(h, dict)] if isinstance(hms, list) else []
    severities = [_hms_severity(entry) for entry in entries]
    unrecognised += [f'hms severity {s}' for s in severities if s not in _HMS_KNOWN]
    serious = sorted(s for s in severities if s in HMS_SEVERITY_STOPS)

    if state_key is None:
        return UNRECOGNISED, None, [NO_MAIN_STATE] + unrecognised
    if state_row is None or state_row[0] == UNRECOGNISED:
        return UNRECOGNISED, None, unrecognised
    if state_row[0] in (ENDED_WELL, ENDED_BADLY):
        return state_row[0], None, unrecognised
    if state_row[0] == NO_PRINT:
        return (ENDED_BADLY if print_error or serious else NO_PRINT), None, unrecognised
    if stage_row is not None and stage_row[0] == WAITING:
        return WAITING, stage_row, unrecognised
    if print_error:
        return WAITING, PRINTER_VALUES[('print_error', 'any other')], unrecognised
    if serious:
        return WAITING, PRINTER_VALUES[('hms severity', serious[0])], unrecognised
    if state_row[0] == WAITING:
        return WAITING, state_row, unrecognised
    return GOING, None, unrecognised


#: What `unrecognised` says of a picture that carries no main state: the printer has sent
#: only partial documents (or none with `gcode_state`) since the daemon connected.
NO_MAIN_STATE = 'no main state (gcode_state) reported yet'


def map_status(report, *, printer=None):
    """Turn one `mqtt_dump()['print']` document into the snapshot the relay stores.

    An empty document means no report has arrived over MQTT, which from the wizard's point
    of view is the printer being unreachable from the daemon's computer."""
    identity = printer or {'model': None, 'name': None, 'serial': None}
    if not isinstance(report, dict) or not report:
        return {'state': UNREACHABLE, 'file': '', 'job_name': '', 'percent': None,
                'remaining_min': None, 'layer': 0, 'layers': 0, 'error': None,
                'stage_code': None, 'stage': None, 'stage_label': None,
                'waiting_for': None, 'waiting_label': None, 'at_the_printer': None,
                'unrecognised': None, 'whole': False, 'printer': identity}

    kind, waiting, unrecognised = classify(report)
    raw_stage = _as_int(report.get('stg_cur'))
    hms = report.get('hms')
    entries = [h for h in hms if isinstance(h, dict)] if isinstance(hms, list) else []
    print_error = _as_int(report.get('print_error'), 0) or 0
    # The most severe HMS entry is the one the status line names, else the print error.
    error = None
    if entries:
        worst = _worst_hms(entries)
        error = format_hms(_as_int(worst.get('attr'), 0) or 0,
                           _as_int(worst.get('code'), 0) or 0)
    elif print_error:
        error = f"PRINT_ERROR_{print_error & 0xFFFFFFFF:08X}"

    # The H2S puts our name, without its extension, in `subtask_name`; `gcode_file` is the
    # G-code path inside the archive (`/data/Metadata/plate_1.gcode`), which names nothing
    # a person or the start check can use. So `file` prefers the subtask name.
    job_name = str(report.get('subtask_name') or '')
    stage, stage_label = printer_stage(raw_stage)
    return {
        'state': CLASS_STATE[kind],
        'waiting_for': waiting[1] if waiting else None,
        'waiting_label': waiting[2] if waiting else None,
        'at_the_printer': waiting[3] if waiting else None,
        'unrecognised': '; '.join(unrecognised)[:200] if unrecognised else None,
        'file': job_name or str(report.get('gcode_file') or ''),
        'job_name': job_name,
        'stage_code': raw_stage,
        'stage': stage,
        'stage_label': stage_label,
        # mc_percent is a whole percent; mc_remaining_time is MINUTES (the library's
        # docstring says seconds, but every Bambu printer documented by OpenBambuAPI
        # reports minutes here). tests/hardware_smoke.py settles it against the real H2S.
        'percent': _as_int(report.get('mc_percent')),
        'remaining_min': _as_int(report.get('mc_remaining_time')),
        'layer': _as_int(report.get('layer_num'), 0),
        'layers': _as_int(report.get('total_layer_num'), 0),
        'error': error,
        # The picture carries the printer's main state. PrinterLink.snapshot narrows it to
        # "since the current connection began" (see "How a start is decided").
        'whole': report.get('gcode_state') not in (None, ''),
        'printer': identity,
    }


class UploadFailed(Exception):
    """The file did not reach the printer whole. `detail` is the evidence for the log."""

    def __init__(self, message, detail=''):
        super().__init__(message)
        self.detail = detail


class UploadCancelled(Exception):
    """The delivery job was cancelled while its file was on its way to the printer."""


#: A socket that moves no byte for this long during an upload is given up on. ftplib has no
#: timeout of its own, so a stalled printer would otherwise hold the job for ever.
UPLOAD_SOCKET_TIMEOUT = 60.0

_LIBRARY_LOGGER = 'bambulabs_api'
# An FTP LIST line: permissions, links, owner, group, size, three date fields, the name.
_LIST_RE = re.compile(r'^\S+\s+\d+\s+\S+\s+\S+\s+(?P<size>\d+)\s+\S+\s+\S+\s+\S+\s+(?P<name>.+)$')


#: What an upload keeps of the library's log as its evidence: at most this many lines, each
#: at most this long. The library logs every 32 kB block it sends at debug level, with the
#: block's bytes in the line; those records are never made (the logger is set to INFO) and
#: never kept, so the evidence is the same small size for any size of file.
CAPTURE_LINES = 20
CAPTURE_LINE_CHARS = 300


class _LibraryLog(logging.Handler):
    """Takes over bambulabs_api's logger. While an upload runs on a thread, that thread's
    records of INFO and above are kept, bounded, as the upload's evidence; otherwise a
    warning or worse becomes one plain line in the daemon's log, and anything quieter is
    dropped."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.forward = None
        self._capturing = {}           # thread id -> list of lines

    def emit(self, record):
        lines = self._capturing.get(threading.get_ident())
        if lines is not None and len(lines) >= CAPTURE_LINES:
            if len(lines) == CAPTURE_LINES:
                lines.append('(more lines from the printer library were dropped)')
            return
        try:
            line = record.getMessage()
        except Exception:              # a malformed record must not break the daemon
            line = str(record.msg)
        line = _one_line(line)[:CAPTURE_LINE_CHARS]
        if lines is not None:
            lines.append(line)
            return
        if record.levelno >= logging.WARNING and self.forward is not None:
            self.forward(f'printer library said: {line}')

    def start_capture(self):
        lines = []
        self._capturing[threading.get_ident()] = lines
        return lines

    def stop_capture(self):
        # Not `release`: that is logging.Handler's own, which unlocks the handler.
        self._capturing.pop(threading.get_ident(), None)


_LIBRARY_LOG = _LibraryLog()


def take_over_library_log(forward):
    """Route bambulabs_api's log through `forward` (see the module docstring)."""
    logger = logging.getLogger(_LIBRARY_LOGGER)
    if _LIBRARY_LOG not in logger.handlers:
        logger.addHandler(_LIBRARY_LOG)
    # INFO, not DEBUG: below it the library logs each upload block's bytes and each whole
    # status document, which would cost memory and time for nothing.
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _LIBRARY_LOG.forward = forward
    return _LIBRARY_LOG


class _CountingReader:
    """The file handed to the library's upload: counts the bytes it reads (which ftplib
    sends at once, block by block) for progress, and stops the upload when cancelled."""

    def __init__(self, handle, total, progress, cancelled):
        self._handle = handle
        self.total = total
        self.sent = 0
        self._progress = progress
        self._cancelled = cancelled
        self.was_cancelled = False

    def read(self, size=-1):
        if self._cancelled is not None and self._cancelled():
            self.was_cancelled = True
            raise UploadCancelled('the delivery job was cancelled during the upload')
        data = self._handle.read(size)
        self.sent += len(data)
        if self._progress is not None and data:
            self._progress(self.sent, self.total)
        return data

    def close(self):
        self._handle.close()

    @property
    def closed(self):
        return self._handle.closed


class PrinterLink:
    """One Bambu printer on the LAN.

    `printer_factory` exists so the tests can substitute a fake for bambulabs_api.Printer
    without the library being installed. `clock` is the monotonic clock the age of the
    printer's report is measured on. `log` receives the library's warnings as plain lines.
    `ports` overrides the printer's MQTT and FTPS ports ({'mqtt': n, 'ftps': n}) for the
    simulated printer; a real printer always uses 8883 and 990."""

    def __init__(self, ip, serial, access_code, *, model=None, name=None,
                 printer_factory=None, clock=time.monotonic, log=None, ports=None):
        self.ip = ip
        self.serial = serial
        self.access_code = access_code
        self.model = model
        self.name = name
        self._factory = printer_factory
        self._printer = None
        self._clock = clock
        self._log = log
        self._ports = ports or {}
        self._last_report = None
        self._last_change_at = None
        # When the printer last sent a status document, on `clock`; set by the library's
        # message callback. None until one arrives, or when the library offers no callback.
        self._document_at = None
        # Whether a document carrying the main state (`gcode_state`) has arrived since the
        # current connection to the printer began. None when the library offers no hooks
        # (a stand-in): then the merged picture alone decides.
        self._whole_since_connect = None
        #: Called with no arguments after each status document, on the library's thread.
        self.on_document = None

    def _document_arrived(self, *args):
        """The library's message callback: the printer has just spoken. The library hands
        the MQTT message last; a document that names the main state makes the picture whole
        for this connection."""
        self._document_at = self._clock()
        if self._whole_since_connect is not None and not self._whole_since_connect:
            self._whole_since_connect = _carries_main_state(args[-1] if args else None)
        if self.on_document is not None:
            self.on_document()

    def _connected(self, *_args):
        """The library's connect callback (also on its own reconnects): until a document
        with the main state arrives, the merged picture is the last connection's, so it
        is not whole."""
        self._whole_since_connect = False

    def _make(self):
        if self._factory is not None:
            printer = self._factory(self.ip, self.access_code, self.serial)
            self._listen(printer)
            return printer
        # Imported here, not at module scope: printer.py must import on a machine without
        # the library so the rest of the daemon's tests still run.
        import bambulabs_api
        printer = bambulabs_api.Printer(self.ip, self.access_code, self.serial)
        self._listen(printer)
        # The library parses each status document inside paho's network thread, and paho
        # re-raises a callback's exception there by default: one document that is not JSON
        # would end the thread, and with it every later status, while the socket stays
        # open. Suppressed, paho logs it (to the library's log, demoted) and goes on.
        printer.mqtt_client._client.suppress_exceptions = True
        if 'ftps' in self._ports:
            printer.ftp_client.port = self._ports['ftps']
        if 'mqtt' in self._ports:
            printer.mqtt_client._port = self._ports['mqtt']
        # Shut the upload's data connection down with a TLS close before closing it. Without
        # it, a TLS 1.3 server's session tickets are left unread, the close turns into a
        # reset, and the end of the file can be lost (the listing then refuses the upload).
        # The library's own option; the size check in upload() stays the guard either way.
        printer.ftp_client.ftps.unwrap = True
        return printer

    def _listen(self, printer):
        """Hear every status document as it arrives, through the library's own hook."""
        client = getattr(printer, 'mqtt_client', None)
        if client is not None and hasattr(client, 'on_message_handler'):
            client.on_message_handler = self._document_arrived
        if client is not None and hasattr(client, 'on_connect_handler'):
            client.on_connect_handler = self._connected
            self._whole_since_connect = False

    def connect(self):
        """Open the MQTT subscription. Deliberately NOT Printer.connect(), which also
        starts the camera: the daemon never needs camera frames, and decoding them through
        Pillow is the one avoidable memory cost when the daemon's computer is small."""
        take_over_library_log(self._log)
        self._printer = self._make()
        self._printer.mqtt_start()
        return self._printer

    def disconnect(self):
        """Close the MQTT connection, then stop the library's network thread. The
        DISCONNECT wakes that thread at once; stopping it alone waits out its one-second
        poll."""
        if self._printer is not None:
            try:
                self._printer.mqtt_client._client.disconnect()
            except Exception:
                pass
            try:
                self._printer.mqtt_stop()
            except Exception:
                pass
            self._printer = None

    def request_report(self):
        """Ask the printer for its whole status document now (the library's `pushall`).
        Used while a wait needs the printer's word and its reports have gone quiet. Never
        raises."""
        try:
            self._require_printer().mqtt_client.pushall()
        except Exception:
            pass

    def _require_printer(self):
        if self._printer is None:
            raise RuntimeError('not connected')
        return self._printer

    @property
    def identity(self):
        return {'model': self.model, 'name': self.name, 'serial': self.serial}

    def raw_report(self):
        """The printer's own report document, or {} when nothing has arrived. Never raises:
        a library that throws, or a document that is not a mapping, must look like an
        unreachable printer, not crash the daemon."""
        if self._printer is None:
            return {}
        try:
            if not self._printer.mqtt_client_connected():
                return {}
            dump = self._printer.mqtt_dump()
            report = dump.get('print') if isinstance(dump, dict) else None
            return dict(report) if isinstance(report, dict) else {}
        except Exception:
            return {}

    def snapshot(self):
        """The status snapshot the daemon posts in every sync, with `report_age_s`: how
        long ago the printer last sent a status document. A printer whose status stream
        went silent while the socket stays open shows up there, not as fresh figures.

        The age survives a disconnect: the library keeps its last document across one, so
        after a reconnect on which the printer has said nothing the old figures come back
        with their old age, never as new. With the library's message callback the age is
        that of the last document received; without one (a stand-in), of the last change
        in what the library holds, where an unreachable spell in between is no change."""
        report = self.raw_report()
        now = self._clock()
        if report and (report != self._last_report or self._last_change_at is None):
            self._last_report = report
            self._last_change_at = now
        if self._last_change_at is None:
            self._last_change_at = now
        spoke_at = self._document_at if self._document_at is not None else self._last_change_at
        snapshot = map_status(report, printer=self.identity)
        snapshot['report_age_s'] = max(0, int(now - spoke_at))
        if self._whole_since_connect is False:
            snapshot['whole'] = False
        return snapshot

    def upload(self, local_path, remote_name, *, progress=None, cancelled=None):
        """Send the sliced file to the printer over FTPS under the job-suffixed name, and
        judge the result by the printer's own listing, not by the FTP reply alone.

        `progress(sent, total)` is called as bytes go; `cancelled()` is asked before each
        block, and a True stops the upload with UploadCancelled. Returns a one-line note
        for the log. Raises UploadFailed when the printer does not have the whole file.

        The library catches any failure during the transfer, logs it and returns None
        (the H2S's 426 after a whole file is the common case); a refused connection or
        login raises. Either way, what decides is the size the printer lists."""
        printer = self._require_printer()
        total = os.path.getsize(local_path)
        reader = _CountingReader(open(local_path, 'rb'), total, progress, cancelled)
        try:
            ftps = printer.ftp_client.ftps
            ftps.timeout = UPLOAD_SOCKET_TIMEOUT
        except AttributeError:
            pass                                       # a stand-in without one
        lines = _LIBRARY_LOG.start_capture()
        try:
            reply = printer.upload_file(reader, remote_name)
        except Exception as e:
            reader.close()
            if reader.was_cancelled:
                raise UploadCancelled(str(e)) from e
            raise UploadFailed(f'the printer refused the upload: {_one_line(e)}',
                               detail='; '.join(lines)) from e
        finally:
            _LIBRARY_LOG.stop_capture()
        if reader.was_cancelled:
            raise UploadCancelled('the delivery job was cancelled during the upload')
        said = '; '.join(lines)
        reply_ok = isinstance(reply, str) and reply.startswith('226')
        listed = self.remote_size(remote_name)
        if listed == total:
            if reply_ok:
                return f'the printer has all {total} bytes'
            return (f'the printer has all {total} bytes (its FTP server answered '
                    f'{_one_line(reply) if reply else "nothing"}; that is harmless)')
        if listed is None and reply_ok:
            return f'sent {total} bytes; the printer did not list its files to confirm'
        evidence = f'reply {reply!r}; library said: {said or "nothing"}'
        if listed is None:
            raise UploadFailed('the printer did not confirm that the file arrived',
                               detail=evidence)
        raise UploadFailed(f'the printer has {listed} of {total} bytes', detail=evidence)

    def remote_size(self, remote_name):
        """The size the printer lists for a file in its top folder, or None when it does
        not list one (or cannot be asked)."""
        try:
            listing = self._require_printer().ftp_client.list_directory()
        except Exception:
            return None
        if not isinstance(listing, (tuple, list)) or len(listing) != 2:
            return None
        for line in listing[1] or []:
            match = _LIST_RE.match(str(line).strip())
            if match and match.group('name') == remote_name:
                return int(match.group('size'))
        return None

    def delete(self, remote_name):
        """Remove a file from the printer, for a cancelled or abandoned upload. The delete
        is always sent, and the printer's answer to it decides; a listing never does (a
        listing may spell a name otherwise, or fail, and prove nothing). Never raises.

        Returns (outcome, the printer's answer in one line): REMOVED, NOT_ON_PRINTER or
        UNCONFIRMED (see their comment). When the printer gave no reply, the second item
        says what happened instead ("no answer: timed out", "no connection: ..."), and
        is_printer_reply tells the two apart. The library swallows a failed delete and logs the
        FTP server's reply as a failure; that log is kept here as the answer, so the
        daemon's log never shows "550 No such file" as an error."""
        lines = _LIBRARY_LOG.start_capture()
        try:
            reply = self._require_printer().delete_file(remote_name)
        except Exception as e:
            return UNCONFIRMED, f'no connection: {_one_line(e)}'
        finally:
            _LIBRARY_LOG.stop_capture()
        if isinstance(reply, str):
            answer = _one_line(reply)
            return (REMOVED if answer[:3] in ('250', '200') else UNCONFIRMED), answer
        failures = [line[len(_LIBRARY_FAILURE):] for line in lines
                    if line.startswith(_LIBRARY_FAILURE)]
        if not failures:
            return UNCONFIRMED, 'no answer'
        answer = failures[-1].strip()
        if not is_printer_reply(answer):
            # The error that ended the delete, not a reply: a timeout or a reset gives its
            # text, a connection dropped during the DELE (ftplib's EOFError) gives none.
            return UNCONFIRMED, f'no answer: {answer or "the connection dropped"}'
        return (NOT_ON_PRINTER if _NO_SUCH_FILE_RE.match(answer) else UNCONFIRMED), answer

    def start(self, remote_name):
        """Start the uploaded file. Plate 1 is what the slicer writes.

        use_ams is False: the slice is single-material, and an AMS mapping the team has not
        asked for would be a surprising default. Revisit if the shop prints from an
        AMS.

        That choice puts the EXTERNAL SPOOL in charge of the material, and the printer
        checks the spool it has against the filament the slice asks for. The fixed profile
        set slices Generic PETG for a 0.6 mm High Flow nozzle on the Textured PEI Plate
        (the slice service's profiles), so an external spool the printer still
        believes is PLA makes the start fail or the print come out wrong. Nothing here can
        detect that: the daemon reports whatever the printer reports.

        Nothing in this call names the plate or the material. Both travel inside the 3MF,
        which is why a profile change upstream needs no change here."""
        return self._require_printer().start_print(
            remote_name, PLATE_NUMBER, use_ams=False, ams_mapping=[0],
            flow_calibration=True)


def _carries_main_state(message):
    """Does this MQTT message's status document name the printer's main state? Never
    raises: a message that is not JSON names nothing."""
    try:
        import json
        document = json.loads(getattr(message, 'payload', b'') or b'')
        report = document.get('print') if isinstance(document, dict) else None
        return isinstance(report, dict) and report.get('gcode_state') not in (None, '')
    except Exception:
        return False


def is_printer_reply(answer):
    """Is this text a reply from the printer's FTP server (three digits first), rather
    than a description of a delete it never answered?"""
    return _FTP_REPLY_RE.match(answer) is not None


def _one_line(value):
    text = str(value) or value.__class__.__name__
    return text.splitlines()[0][:200] if text.splitlines() else text[:200]


def discover(timeout=5.0, *, sock_factory=None, clock=None):
    """Listen for Bambu printers announcing themselves on UDP 2021.

    Returns a list of {'serial', 'model', 'name', 'ip'}. School networks often block
    broadcasts, so `pair` treats an empty list as normal and asks for an IP address.

    `clock` is the monotonic clock the deadline is measured on, injected by the tests.

    PROVISIONAL: the exact SSDP header names are not yet confirmed on the H2S. The parser below
    accepts any `Key: value` header line and reads the ones Bambu is documented to send, so
    an unexpected name shows up as a missing field rather than a crash."""
    import time as _time

    clock = clock or _time.monotonic
    if sock_factory is not None:
        sock = sock_factory()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', DISCOVERY_PORT))
    # Join the SSDP group on every interface. A network (or a container) that refuses
    # membership is not fatal: some setups deliver the announcements to the plain bound
    # port anyway, so fall through and listen rather than give up.
    try:
        mreq = socket.inet_aton(DISCOVERY_GROUP) + socket.inet_aton('0.0.0.0')
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except OSError:
        pass
    sock.settimeout(1.0)

    found = {}
    deadline = clock() + timeout
    try:
        while clock() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                # A real socket error (the interface went away, the socket was closed)
                # will not fix itself; spinning on it until the deadline helps nobody.
                break
            headers = {}
            for line in data.decode('utf-8', 'replace').splitlines():
                key, sep, value = line.partition(':')
                if sep:
                    headers[key.strip().lower()] = value.strip()
            serial = headers.get('usn') or headers.get('devserial.bambu.com')
            if not serial:
                continue
            found[serial] = {
                'serial': serial,
                'model': headers.get('devmodel.bambu.com', ''),
                'name': headers.get('devname.bambu.com', ''),
                'ip': addr[0],
            }
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return list(found.values())
