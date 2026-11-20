"""Error reports (contracts/error-report.md) for every failure printer delivery can report.

Every failure has a stable code in CODES, with the sentence a student reads, the remedy,
whether the same request may succeed if sent again, and where it happened. A failure is
reported from where it happens, by its code:

- the daemon acknowledges a failed delivery job with the code (`delivery.upload_failed`,
  say) and the underlying evidence in `detail`;
- the relay builds its own refusals, expiries and print outcomes by code.

The relay's refusals still travel beside the error report as the one line of text they
always were (the `error` of a refused send, the `reason` of a failed job), and a daemon
that sends no code (one older than this version) is still understood: `error_report(text)`
matches the texts in RULES to a code, falling through to `delivery.job_failed`.

`detail` is the underlying evidence, with any download token cut out, since a download
path is a bearer credential. No pairing code, access code or token ever reaches a report.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

_DOWNLOAD_TOKEN_RE = re.compile(r'(/download/)[^\s\'"]+')
# A bearer token or signed daemon credential that slipped into an exception's text.
_BEARER_RE = re.compile(r'(Bearer\s+)[^\s\'"]+')


@dataclass(frozen=True)
class Code:
    message: str            # may use {fields}; a part in [...] that names a field goes
                            # when that field is missing (see fill)
    remedy: str
    retryable: bool
    stage: Optional[str] = None
    action: Optional[str] = None


#: Every code printer delivery can report. The guide lists the same codes; each has a test
#: that produces it on purpose.
CODES = {
    # -- refused before any delivery job exists ------------------------------------------
    'delivery.no_session': Code(
        'The printer service could not tell which team this request came from.',
        'Sign in again, then send the print once more.', False, 'send'),
    'delivery.identity_unreadable': Code(
        'The printer service could not read which team sent this print.',
        'Sign in again, then send the print once more.', False, 'send'),
    'delivery.sliced_file_unreadable': Code(
        'The printer service could not read the sliced file for this print.',
        'Send the print again in a moment, and slice the plate again if it fails twice.',
        True, 'send'),
    'delivery.not_paired': Code(
        'No printer is paired with this team yet.',
        'Ask a mentor to pair the shop printer, then send the print again.', False, 'send'),
    'delivery.sliced_file_missing': Code(
        'The sliced file for this print is no longer available.',
        'Slice the plate again and send the new file.', False, 'send', 'slice_again'),
    'delivery.sliced_file_too_old': Code(
        'This sliced file is too old to send to the printer.',
        'Slice the plate again and send the new file.', False, 'send', 'slice_again'),
    'delivery.daemon_never_reported': Code(
        'The computer next to the printer has not checked in since the printer service '
        'started.',
        'Ask a mentor to check that the printer computer is switched on and online.',
        True, 'send'),
    'delivery.no_printer_status': Code(
        'The printer has not reported its status yet.',
        'Wait a moment, then send the print again.', True, 'send'),
    'delivery.daemon_silent': Code(
        'The computer next to the printer was last heard from[ {minutes} minutes ago| a '
        'while ago].',
        'Check that the computer next to the printer is switched on and online, then send '
        'the print again.', True, 'send'),
    'delivery.printer_busy': Code(
        'The printer is busy printing[ {name}| a file][, {percent} percent done].',
        'Wait for that print to finish, then send this one.', True, 'send'),
    'delivery.printer_paused': Code(
        'The printer has a paused print[, {name},] waiting for someone.',
        'Ask someone at the printer to resume or cancel the paused print, then send this '
        'one.', True, 'send'),
    'delivery.printer_unreachable': Code(
        'The computer next to the printer cannot reach the printer.',
        'Check that the printer is switched on and on the shop network, then send the '
        'print again.', True, 'send'),
    'delivery.printer_state_unrecognised': Code(
        'The printer reported something this version of printer delivery does not know, '
        'so it cannot tell whether the printer is free.',
        'Check the printer, then try again in a moment.', True, 'send'),
    'delivery.job_in_flight': Code(
        'Another print is already on its way to the printer.',
        'Wait until that print has started, then send this one.', True, 'send'),
    'delivery.rate_limited': Code(
        'Too many requests reached the printer service in a short time.',
        'Wait a minute, then try again.', True),
    'delivery.relay_failed': Code(
        'The printer service failed while handling this request.',
        'Try again in a moment, and tell a mentor if it keeps happening.', True),
    'delivery.job_unknown': Code(
        'The printer service has no record of this print, perhaps because it restarted.',
        'Look at the printer to see whether the part is printing before sending it again.',
        False),
    'delivery.cancel_too_late': Code(
        'This print has already been started on the printer, so it can no longer be '
        'cancelled from here.',
        'Stop the print on the printer\'s own screen if it should not go on.', False,
        'starting'),
    'delivery.already_finished': Code(
        'This print has already ended, so there is nothing to cancel or stop following.',
        'Look at the print\'s last report to see how it ended.', False),
    'delivery.still_reporting': Code(
        'The printer is still reporting this print, so it is running and can only be '
        'stopped at the printer.',
        'Stop the print on the printer\'s own screen if it should not go on.', False,
        'printing'),
    'delivery.not_started': Code(
        'This print has not been started on the printer yet, so there is nothing to stop '
        'following.',
        'Cancel the print instead if it should not go ahead.', False, None, 'cancel'),
    'delivery.start_without_instance': Code(
        'The computer next to the printer asked to start a print without naming itself, so '
        'the printer service did not let it start.',
        'Ask a mentor to update the printer computer\'s software to the current version.',
        False, 'starting'),
    'delivery.request_too_large': Code(
        'The request was too large for the printer service.',
        'Tell a mentor: the computer next to the printer or the page sent far more than it '
        'should.', False),
    # -- a delivery job that ended before the print started -----------------------------
    'delivery.job_not_picked_up': Code(
        'The computer next to the printer did not collect the print in time.',
        'Check that the printer computer is switched on and online, then send the print '
        'again.', True, 'waiting_for_daemon'),
    'delivery.job_not_confirmed': Code(
        'The computer next to the printer collected the print and was then not heard from '
        '[for {minutes} minutes|for too long], so the print was given up before it started.',
        'Check that the printer computer is switched on and online, then send the print '
        'again.', True),
    'delivery.cancelled': Code(
        'The print was cancelled before it started.',
        'Send the print again when you are ready.', True),
    'delivery.printer_unreachable_at_start': Code(
        'The computer next to the printer could not reach the printer[ for {minutes} '
        'minutes].',
        'Check that the printer is switched on and on the shop network, then send the '
        'print again.', True, 'waiting_for_printer'),
    'delivery.printer_busy_at_start': Code(
        'The printer was busy with another print[, {name}][, {percent} percent done], when '
        'this one arrived.',
        'Wait for that print to finish, then send this one.', True, 'waiting_for_printer'),
    'delivery.printer_state_unrecognised_at_start': Code(
        'The printer reported something this version of printer delivery does not know '
        'when the print arrived, so it was not started.',
        'Check the printer, then send the print again in a moment.', True,
        'waiting_for_printer'),
    'delivery.printer_error_at_start': Code(
        'The printer showed an error when the print was sent{meaning}.',
        'Ask someone at the printer to clear the error on its screen, then send the print '
        'again.', True, 'starting'),
    'delivery.download_failed': Code(
        'The computer next to the printer could not fetch the sliced file.',
        'Send the print again, and ask a mentor to check the printer computer\'s network '
        'if it fails twice.', True, 'downloading'),
    'delivery.download_corrupt': Code(
        'The sliced file arrived damaged at the computer next to the printer.',
        'Send the print again, and ask a mentor to check the printer computer\'s network '
        'if it fails twice.', True, 'downloading'),
    'delivery.upload_failed': Code(
        'The file could not be sent to the printer.',
        'Check that the printer is switched on and on the shop network, then send the '
        'print again.', True, 'uploading'),
    'delivery.start_refused': Code(
        'The printer refused to start the print.',
        'Check the printer screen for a message, then send the print again.', True,
        'starting'),
    'delivery.start_timeout': Code(
        'The printer did not show the print as started[ within {seconds} seconds| in '
        'time].',
        'Look at the printer before sending again, because the part may be printing '
        'already.', False, 'starting'),
    'delivery.start_other_file': Code(
        'The printer started a different file[, {name},] instead of this print.',
        'Look at the printer: stop the other print if nobody meant to start it, then send '
        'this one again.', False, 'starting'),
    'delivery.job_failed': Code(
        'The printer computer could not pass the print on to the printer.',
        'Send the print again, and ask a mentor to check the printer computer if it fails '
        'twice.', True),
    # -- a print that started -----------------------------------------------------------
    'delivery.print_failed': Code(
        'The print failed partway through{meaning}.',
        'Look at the printer and clear its screen, then send the print again.', True,
        'printing'),
    'delivery.print_stopped': Code(
        'The print was stopped at the printer.',
        'Send the print again if it should be printed after all.', True, 'printing'),
    'delivery.print_vanished': Code(
        'The printer stopped reporting this print without saying it finished.',
        'Look at the printer to see whether the part is complete.', False, 'printing'),
    'delivery.outcome_unknown': Code(
        'Contact with the printer was lost after the print started, so the printer service '
        'cannot tell whether the print is still running or has finished.',
        'Check the printer to see whether the part printed, and send it again only if it '
        'did not.', False, 'printing'),
}


#: The texts the relay and older daemons produce, matched in order to a code. The named
#: groups fill the code's message.
RULES = (
    ('delivery.no_session', r'Session verification required\.'),
    ('delivery.identity_unreadable', r'Could not read who is asking: (?P<error>.*)'),
    ('delivery.sliced_file_unreadable', r'Could not read the sliced file: (?P<error>.*)'),
    ('delivery.not_paired', r'No printer paired'),
    ('delivery.sliced_file_missing', r'File not found or expired'),
    ('delivery.sliced_file_too_old', r'slice again'),
    ('delivery.daemon_never_reported',
     r'The Pi has not reported since the service started; check the setup guide\.'),
    ('delivery.no_printer_status', r'No printer reporting yet; try again in a moment\.'),
    ('delivery.daemon_silent', r'Printer offline, last seen (?P<minutes>\d+) min ago'),
    ('delivery.printer_busy',
     r'Printer busy, printing (?P<name>.*?)(?: at (?P<percent>\d+) percent)?'),
    ('delivery.printer_paused', r'Paused, (?P<name>.*)'),
    ('delivery.printer_unreachable', r'Printer unreachable from the Pi'),
    ('delivery.printer_state_unrecognised', r'Printer state not recognised: (?P<value>.*)'),
    ('delivery.job_in_flight', r'A job is already on its way to the printer'),
    ('delivery.rate_limited', r'Too Many Requests: .*'),
    ('delivery.relay_failed', r'The printer service failed: (?P<error>.*)'),
    ('delivery.job_not_picked_up', r'printer did not pick up the job'),
    ('delivery.job_not_confirmed', r'printer did not confirm the job'),
    ('delivery.start_refused', r'the printer refused the print start command'),
    ('delivery.start_timeout', r'the printer did not start the file within (?P<seconds>\d+)s'),
    ('delivery.printer_error_at_start', r'printer error: (?P<error>.*)'),
)

FALLBACK = 'delivery.job_failed'

_COMPILED = tuple((code, re.compile(pattern)) for code, pattern in RULES)

#: What a printer's error code means, where the meaning is known. PROVISIONAL: taken from
#: the HMS and print-error tables Bambu publishes on its wiki, not from the H2S itself; an
#: unknown code still gives a truthful report with the code in `detail`.
PRINTER_ERROR_MEANINGS = {
    'PRINT_ERROR_0300400C': 'the print was cancelled',
    'PRINT_ERROR_07008011': 'the filament ran out',
    'PRINT_ERROR_07FF8011': 'the filament ran out',
    'PRINT_ERROR_03008001': 'the printer paused for a user command',
    'PRINT_ERROR_0300800A': 'a problem was detected on the first layer',
    'PRINT_ERROR_03004002': 'the nozzle may be clogged',
    'PRINT_ERROR_0500400E': 'the front door or the top cover is open',
    'HMS_0300_0100_0001_0007': 'the heated bed is not heating properly',
    'HMS_0300_0D00_0001_0003': 'the build plate is not placed properly',
    'HMS_0700_2000_0002_0001': 'the filament ran out',
    'HMS_0C00_0300_0003_0008': 'spaghetti-like failure was detected',
}

#: The printer error codes that mean someone stopped the print at the printer.
PRINTER_STOP_CODES = frozenset({'PRINT_ERROR_0300400C'})


#: The most characters of evidence an error report's `detail` carries, and of a daemon's
#: one line of reason. A report travels in every status answer and stream event, so
#: nothing in it may grow with the size of a sliced file.
MAX_DETAIL_CHARS = 2000
MAX_REASON_CHARS = 300

#: The figures a daemon may send beside a failure's code, to fill its sentence, and how
#: long each may be.
FIELD_NAMES = frozenset({'seconds', 'minutes', 'name', 'percent', 'error'})
MAX_FIELD_CHARS = 120


def capped(text, limit=MAX_DETAIL_CHARS):
    """The text cut to `limit` characters, saying how much was cut."""
    if len(text) <= limit:
        return text
    note = f' ... [{len(text) - limit} more characters cut]'
    return text[:max(0, limit - len(note))] + note


def redact(text):
    """The text with any download token or bearer credential replaced."""
    text = _DOWNLOAD_TOKEN_RE.sub(r'\1<token>', text or '')
    return _BEARER_RE.sub(r'\1<token>', text)


def reason_text(value, limit=MAX_REASON_CHARS):
    """A daemon's acknowledgement `error` as the relay stores it: None when there is no
    reason (any empty value), else one string with any download token cut out, at most
    `limit` characters. A number, a list or an object is kept as its JSON text."""
    if not value:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, default=str)
    return capped(redact(value[:limit * 4]), limit)


def daemon_fields(value):
    """The figures a daemon sent beside a failure's code, kept only when they are known
    names with short plain values; anything else is dropped."""
    if not isinstance(value, dict):
        return {}
    kept = {}
    for key, item in value.items():
        if key not in FIELD_NAMES or isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            kept[key] = item
        elif isinstance(item, str) and item:
            kept[key] = redact(item[:MAX_FIELD_CHARS])
    return kept


def exception_text(error):
    """One line naming an exception, for the `error` text and `detail`."""
    name = error.__class__.__name__
    lines = str(error).splitlines()
    text = f'{name}: {lines[0]}' if lines and lines[0] else name
    return redact(text[:200])


def meaning_of(printer_error):
    """', which means <meaning>' for a known printer error code, else ''."""
    meaning = PRINTER_ERROR_MEANINGS.get(printer_error or '')
    return f': {meaning}' if meaning else ''


#: `[text with {figures}|otherwise]` in a message: the text when every figure in it is
#: known, else `otherwise` (or nothing). A missing figure never reaches a sentence as
#: "None" or "unknown": every figure in CODES sits inside such a part (`meaning` aside,
#: which is always set), and a test renders every message with none of them.
_OPTIONAL_RE = re.compile(r'\[([^\[\]|]*)(?:\|([^\[\]]*))?\]')
_FIELD_RE = re.compile(r'\{(\w+)\}')


def _known(value):
    return value is not None and str(value) not in ('', 'None', 'unknown')


def fill(message, values):
    """The message with its figures filled in, dropping each optional part whose figures
    are not all known."""
    def choose(match):
        part, otherwise = match.group(1), match.group(2) or ''
        if all(_known(values.get(name)) for name in _FIELD_RE.findall(part)):
            return part
        return otherwise
    return _OPTIONAL_RE.sub(choose, message).format_map(values)


def report_for_code(code, *, detail='', **fields):
    """The error report for `code`. An unknown code (from a newer daemon, say) is reported
    truthfully as `delivery.job_failed` with the code it came with kept in `detail`."""
    definition = CODES.get(code)
    if definition is None:
        detail = f'code {code!r} from the daemon; {detail}' if code else detail
        code, definition = FALLBACK, CODES[FALLBACK]
    values = {k: v for k, v in fields.items() if v is not None}
    values.setdefault('meaning', '')
    if not isinstance(detail, str):
        detail = reason_text(detail, MAX_DETAIL_CHARS) or ''
    report = {
        'code': code,
        'message': fill(definition.message, values),
        'remedy': definition.remedy,
        'retryable': definition.retryable,
        # Cut before the redaction runs, so a huge text costs nothing; cut again after.
        'detail': capped(redact(detail[:MAX_DETAIL_CHARS * 2])),
    }
    if definition.stage:
        report['where'] = {'stage': definition.stage}
    if definition.action:
        report['action'] = definition.action
    return report


def rule_for(text):
    """(code, match) for one of the relay's failure texts; (FALLBACK, None) for any other."""
    for code, pattern in _COMPILED:
        match = pattern.fullmatch(text)
        if match:
            return code, match
    return FALLBACK, None


def error_report(text, *, code=None, detail=None, fields=None):
    """The error report for one failure the relay reported as `text`.

    With `code` (a daemon that names its failure) the code decides, filled from the
    daemon's `fields` (see daemon_fields); the text is the detail unless a detail is
    given. Without it the text is matched against RULES."""
    if text is None:
        text = ''
    elif not isinstance(text, str):
        text = reason_text(text) or ''
    if code:
        values = daemon_fields(fields)
        if 'error' in values:
            values['meaning'] = meaning_of(values['error'])
        return report_for_code(code, detail=detail if detail else text, **values)
    matched, match = rule_for(text)
    fields = match.groupdict() if match else {}
    if matched == 'delivery.printer_error_at_start':
        fields['meaning'] = meaning_of(fields.get('error'))
    return report_for_code(matched, detail=text, **fields)
