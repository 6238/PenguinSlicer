"""The adapter from the relay's failures to error reports (contracts/error-report.md).

The relay reports a failure to its caller as one line of text: the `error` of a refused
send, or the `reason` of a job that failed. The port keeps those texts exactly as they
were, and this module turns each of them into an error report, which the routes add beside
the text as `error_report`.

The adapter matches the texts the relay and the daemon actually produce, in the order of
RULES. That makes it as fragile as the texts are: a daemon that changes a reason without
changing this table falls through to `delivery.job_failed`. Hardening replaces the matching
with codes carried from where each failure happens.

`detail` is the original text, with any download token cut out, since a download path is a
bearer credential.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

_DOWNLOAD_TOKEN_RE = re.compile(r'(/download/)[^\s\'"]+')


@dataclass(frozen=True)
class Rule:
    code: str
    pattern: str            # matched against the whole text, case-sensitively
    message: str            # may use the pattern's named groups
    remedy: str
    retryable: bool
    stage: Optional[str] = None
    action: Optional[str] = None


#: Every failure the relay can report to its caller, in matching order. The README lists the
#: same codes; each has a test that produces it.
RULES = (
    # -- a send refused before any job exists ------------------------------------------
    Rule('delivery.no_session', r'Session verification required\.',
         'The printer service could not tell which team this request came from.',
         'Sign in again, then send the print once more.', False, 'send'),
    Rule('delivery.identity_unreadable', r'Could not read who is asking: (?P<error>.*)',
         'The printer service could not read which team sent this print.',
         'Sign in again, then send the print once more.', False, 'send'),
    Rule('delivery.sliced_file_unreadable', r'Could not read the sliced file: (?P<error>.*)',
         'The printer service could not read the sliced file for this print.',
         'Send the print again in a moment, and slice the plate again if it fails twice.',
         True, 'send'),
    Rule('delivery.not_paired', r'No printer paired',
         'No printer is paired with this team yet.',
         'Ask a mentor to pair the shop printer, then send the print again.', False, 'send'),
    Rule('delivery.sliced_file_missing', r'File not found or expired',
         'The sliced file for this print is no longer available.',
         'Slice the plate again and send the new file.', False, 'send', 'slice_again'),
    Rule('delivery.sliced_file_too_old', r'slice again',
         'This sliced file is too old to send to the printer.',
         'Slice the plate again and send the new file.', False, 'send', 'slice_again'),
    Rule('delivery.daemon_never_reported',
         r'The Pi has not reported since the service started; check the setup guide\.',
         'The computer next to the printer has not checked in since the printer service '
         'started.',
         'Ask a mentor to check that the printer computer is switched on and online.',
         True, 'send'),
    Rule('delivery.no_printer_status', r'No printer reporting yet; try again in a moment\.',
         'The printer has not reported its status yet.',
         'Wait a moment, then send the print again.', True, 'send'),
    Rule('delivery.printer_offline', r'Printer offline, last seen (?P<minutes>\d+) min ago',
         'The printer was last heard from {minutes} minutes ago.',
         'Check that the printer and the computer next to it are switched on and online, '
         'then send the print again.', True, 'send'),
    Rule('delivery.printer_busy', r'Printer busy, printing (?P<name>.*) at (?P<percent>.*) percent',
         'The printer is busy with another print.',
         'Wait for that print to finish, then send this one.', True, 'send'),
    Rule('delivery.printer_paused', r'Paused, (?P<name>.*)',
         'The printer has a paused print waiting for someone.',
         'Ask someone at the printer to resume or cancel the paused print, then send this '
         'one.', True, 'send'),
    Rule('delivery.printer_unreachable', r'Printer unreachable from the Pi',
         'The computer next to the printer cannot reach the printer.',
         'Check that the printer is switched on and on the shop network, then send the '
         'print again.', True, 'send'),
    Rule('delivery.printer_error', r'Printer error: (?P<error>.*)',
         'The printer is showing an error.',
         'Ask someone at the printer to clear the error on its screen, then send the print '
         'again.', True, 'send'),
    Rule('delivery.job_in_flight', r'A job is already on its way to the printer',
         'Another print is already on its way to the printer.',
         'Wait until that print has started, then send this one.', True, 'send'),
    Rule('delivery.rate_limited', r'Too Many Requests: .*',
         'Too many requests reached the printer service in a short time.',
         'Wait a minute, then try again.', True),
    # -- a job that ended without starting -----------------------------------------------
    Rule('delivery.job_not_picked_up', r'printer did not pick up the job',
         'The computer next to the printer did not collect the print in time.',
         'Check that the printer computer is switched on and online, then send the print '
         'again.', True, 'pick_up'),
    Rule('delivery.job_not_confirmed', r'printer did not confirm the job',
         'The print was collected but the printer computer never said whether it started.',
         'Look at the printer before sending again, because the part may be printing '
         'already.', False, 'start'),
    Rule('delivery.start_refused', r'the printer refused the print start command',
         'The printer refused to start the print.',
         'Check the printer screen for a message, then send the print again.', True,
         'start'),
    Rule('delivery.start_timeout',
         r'the printer did not start the file within (?P<seconds>\d+)s',
         'The printer did not show the print as started within {seconds} seconds.',
         'Look at the printer before sending again, because the part may be printing '
         'already.', False, 'start'),
    Rule('delivery.printer_error_at_start', r'printer error: (?P<error>.*)',
         'The printer showed an error when the print was sent.',
         'Ask someone at the printer to clear the error on its screen, then send the print '
         'again.', True, 'start'),
)

#: What any other failed job becomes: the daemon's one-line reason for a download, upload
#: or unexpected failure, or a failed acknowledgement with no reason at all.
FALLBACK = Rule('delivery.job_failed', r'.*',
                'The printer computer could not pass the print on to the printer.',
                'Send the print again, and ask a mentor to check the printer computer if '
                'it fails twice.', True)

_COMPILED = tuple((rule, re.compile(rule.pattern)) for rule in RULES)


def redact(text):
    """The text with any download token replaced, for `detail` and for logs."""
    return _DOWNLOAD_TOKEN_RE.sub(r'\1<token>', text or '')


def reason_text(value):
    """A daemon's acknowledgement `error` as the relay stores it: None when there is no
    reason (any empty value, as before), else one string with any download token cut out.
    The daemon sends a string, but the relay does not trust it to: a number, a list or an
    object is kept as its JSON text, so the status line can still build an error report
    from it."""
    if not value:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, default=str)
    return redact(value)


def exception_text(error):
    """One line naming a caller function's exception, for the `error` text and `detail`."""
    name = error.__class__.__name__
    lines = str(error).splitlines()
    text = f'{name}: {lines[0]}' if lines and lines[0] else name
    return redact(text[:200])


def rule_for(text):
    for rule, pattern in _COMPILED:
        match = pattern.fullmatch(text)
        if match:
            return rule, match
    return FALLBACK, None


def error_report(text):
    """The error report for one failure the relay reported as `text`."""
    if text is None:
        text = ''
    elif not isinstance(text, str):
        text = reason_text(text) or ''
    rule, match = rule_for(text)
    groups = match.groupdict() if match else {}
    report = {
        'code': rule.code,
        'message': rule.message.format(**groups),
        'remedy': rule.remedy,
        'retryable': rule.retryable,
        'detail': redact(text),
    }
    if rule.stage:
        report['where'] = {'stage': rule.stage}
    if rule.action:
        report['action'] = rule.action
    return report
