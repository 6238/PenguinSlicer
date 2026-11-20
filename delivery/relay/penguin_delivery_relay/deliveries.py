"""Delivery jobs and their progress reports (contracts/progress-report.md).

A delivery job is one sliced file's way from a send to the end of its print. The relay's
job slot (relay.py) holds a job only until the daemon acknowledges the start; the delivery
job here lives on after that, following the print through the printer's own reports, until
it reaches a final state.

States are the contract's: `queued`, `running`, `done`, `failed`, `cancelled`, the last
three final. Stages, in order:

| Stage | State | Comes from |
|---|---|---|
| `waiting_for_daemon` | queued | the send; the daemon has not collected the job |
| `waiting_for_printer` | running | the daemon: the printer is off or unreachable |
| `downloading` | running | the daemon fetching the sliced file |
| `uploading` | running | the daemon sending it to the printer, `fraction` from bytes sent |
| `starting` | running | the start command and the wait for the printer to report it |
| `printing` | running | the printer's reports; `printer_stage`, `percent`, `layer`, `total_layers`, `remaining_min` beside it |
| `waiting_for_person` | running | the printer's reports: the print is under way, but the printer waits for someone (a pause, an error code, a door open, filament run out); `waiting_for`, `waiting_label`, `at_the_printer`, `printer_error`, `printer_error_meaning` beside it. Back to `printing` when it resumes |

Nothing here waits or reads a clock of its own: every method takes `now` from the relay's
injected clock, and the relay's lock guards every call.
"""

from . import errors

QUEUED, RUNNING, DONE, FAILED, CANCELLED = 'queued', 'running', 'done', 'failed', 'cancelled'
FINAL = frozenset({DONE, FAILED, CANCELLED})

STAGES = (
    ('waiting_for_daemon', 'Waiting for the computer next to the printer'),
    ('waiting_for_printer', 'Waiting for the printer to answer'),
    ('downloading', 'The computer next to the printer is fetching the file'),
    ('uploading', 'Sending the file to the printer'),
    ('starting', 'Starting the print'),
    ('printing', 'Printing'),
    ('waiting_for_person', 'The printer is waiting for someone'),
)
STAGE_LABELS = dict(STAGES)
#: The stages a daemon may report for a job it holds; the two below are the relay's.
DAEMON_STAGES = frozenset({'waiting_for_printer', 'downloading', 'uploading', 'starting'})
#: The stages in which the relay follows the print through the printer's own reports.
FOLLOWING = frozenset({'printing', 'waiting_for_person'})
#: Past the start gate, this long with no fresh word (the daemon silent, or the printer
#: unreachable or quiet) and the relay stops following the delivery job by itself: it ends
#: `failed` with `delivery.outcome_unknown`, which says the outcome is not known. The one
#: place where time ends a delivery job.
OUTCOME_UNKNOWN_AFTER_SECONDS = 24 * 60 * 60
#: What to do at the printer when the daemon's snapshot names no remedy.
AT_THE_PRINTER = "Look at the printer's screen, deal with what it shows, then resume the print there."

#: How far through the whole delivery job each stage begins and ends, for `fraction`.
#: The print itself is most of it; the split before it is a convention, not a measurement.
STAGE_SPAN = {
    'waiting_for_daemon': (0.0, 0.0),
    'waiting_for_printer': (0.0, 0.0),
    'downloading': (0.0, 0.02),
    'uploading': (0.02, 0.08),
    'starting': (0.08, 0.10),
    'printing': (0.10, 1.0),
    'waiting_for_person': (0.10, 1.0),
}

#: No word from the daemon for this long, and a running report is marked stale.
STALE_AFTER_SECONDS = 20
#: The printer's own report unchanged for this long during a print, and it is marked stale.
PRINTER_QUIET_SECONDS = 60
#: A print the printer's own reports stop showing as under way (another file, no file, or
#: idle with ours still named), for this long, has vanished. Only reports count: an
#: unreachable printer or a silent daemon never makes a print vanish.
PRINT_VANISH_SECONDS = 120
#: The printer states in which a print of ours is under way or has ended with a report.
_FOLLOWED = frozenset({'running', 'paused', 'finished', 'error'})
#: The snapshot state of a printer whose main state the daemon does not know. A followed
#: print under it is never ended or vanished, and counts as stale (so stop-following works).
UNRECOGNISED_STATE = 'unrecognised'
#: A final delivery job's last report is kept this long for a late caller, whatever ended
#: it (the 24-hour rule included): a caller that polls slowly still learns how it ended.
FINAL_TTL_SECONDS = 24 * 60 * 60

_EXTRAS = ('printer_stage', 'printer_stage_label', 'percent', 'layer', 'total_layers',
           'remaining_min', 'bytes_sent', 'bytes_total', 'cancel_requested', 'waiting_for',
           'waiting_label', 'at_the_printer', 'printer_error', 'printer_error_meaning',
           'unrecognised')


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


class Delivery:
    """One delivery job. Plain attributes; the relay's lock guards every access."""

    def __init__(self, job_id, code, *, filename, team_number, now):
        self.job_id = job_id
        self.code = code
        self.filename = filename
        self.team_number = team_number
        self.created_at = now
        self.running_since = None
        self.state = QUEUED
        self.stage = 'waiting_for_daemon'
        self.stage_fraction = None
        self.extras = {}
        self.error = None
        self.sequence = 0
        self.last_word_at = now
        self.printer_quiet_s = None
        self.printer_unreachable = False
        self.printer_unrecognised = False
        self.not_seen_since = None
        self.finished_at = None
        self.stale_age = None
        self.cancel_requested = False
        self.start_granted_to = None
        #: The start gate was passed (or the printer named the file): from here the file
        #: may be printing, so only the printer's word, or stop_following, ends the job.
        self.gate_passed = False
        #: When the job last had fresh word (not stale), for OUTCOME_UNKNOWN_AFTER_SECONDS.
        self.fresh_at = now
        self.report = None
        self.transitions = []          # (state, stage) in order, for the log and the tests
        self._emit(now)

    # -- the report ---------------------------------------------------------------------

    @property
    def final(self):
        return self.state in FINAL

    def _fraction(self):
        if self.state == DONE:
            return 1.0
        if self.stage_fraction is None or self.state in FINAL:
            return None
        low, high = STAGE_SPAN[self.stage]
        return round(low + (high - low) * max(0.0, min(1.0, self.stage_fraction)), 4)

    def _build(self, now):
        report = {
            'job': self.job_id,
            'state': self.state,
            'stage': self.stage,
            'stage_label': STAGE_LABELS[self.stage],
            'elapsed_s': round(now - self.running_since, 1) if self.running_since else 0.0,
            'sequence': self.sequence,
            'file': self.filename,
        }
        fraction = self._fraction()
        if fraction is not None:
            report['fraction'] = fraction
        remaining = self.extras.get('remaining_min')
        if self.stage == 'printing' and remaining is not None and self.state == RUNNING:
            report['expected_s'] = round(report['elapsed_s'] + 60 * remaining, 1)
        for key in _EXTRAS:
            if self.extras.get(key) is not None:
                report[key] = self.extras[key]
        if self.cancel_requested and not self.final:
            report['cancel_requested'] = True
        if self.stale_age is not None:
            report['stale'] = True
            report['stale_age_s'] = int(self.stale_age)
        if self.error is not None:
            report['error'] = self.error
        return report

    def _emit(self, now):
        """A new report: the sequence goes up by one, and the transition is recorded when
        the state or the stage changed."""
        previous = self.report
        self.sequence += 1
        self.report = self._build(now)
        if previous is None or (previous['state'], previous['stage']) != (self.state, self.stage):
            self.transitions.append((self.state, self.stage))
        return self.report

    def _change(self, now, **values):
        """Apply values; emit a report only if anything a caller sees changed."""
        if self.final:
            return False
        before = (self.state, self.stage, self.stage_fraction, dict(self.extras),
                  self.cancel_requested, self.stale_age is not None)
        for key, value in values.items():
            if key == 'extras':
                self.extras.update(value)
            else:
                setattr(self, key, value)
        after = (self.state, self.stage, self.stage_fraction, dict(self.extras),
                 self.cancel_requested, self.stale_age is not None)
        if before == after:
            return False
        if self.state in FINAL:
            self.finished_at = now
            self.stale_age = None
        self._emit(now)
        return True

    # -- events -------------------------------------------------------------------------

    def handed_out(self, now):
        if self.state == QUEUED:
            self.running_since = now
            self._change(now, state=RUNNING)

    def heard(self, now):
        """The daemon spoke for this job's printer. The stale marker is worked out again by
        `refresh`, after the sync's snapshot has been read: a daemon that speaks for a
        printer it cannot reach is word, but not word from the printer."""
        self.last_word_at = now

    def printer_has_it(self, snapshot):
        """Does the printer's report name this job's file as a print under way or ended?"""
        return snapshot.get('state') in _FOLLOWED and self._names_us(snapshot)

    def _names_us(self, snapshot):
        return (self.job_id in (snapshot.get('job_name') or '')
                or self.job_id in (snapshot.get('file') or ''))

    def daemon_progress(self, progress, now):
        """A stage the daemon reports for the job it holds. Anything else is ignored."""
        stage = progress.get('stage')
        if stage not in DAEMON_STAGES or self.stage in FOLLOWING:
            return
        extras = {}
        sent, total = _number(progress.get('bytes_sent')), _number(progress.get('bytes_total'))
        fraction = None
        if sent is not None and total:
            fraction = max(0.0, min(1.0, sent / total))
            extras = {'bytes_sent': int(sent), 'bytes_total': int(total)}
        elif _number(progress.get('fraction')) is not None:
            fraction = max(0.0, min(1.0, progress['fraction']))
        if stage != self.stage:
            self.extras.pop('bytes_sent', None)
            self.extras.pop('bytes_total', None)
        if self.state == QUEUED:
            self.running_since = now
        self._change(now, state=RUNNING, stage=stage, stage_fraction=fraction, extras=extras)

    def started(self, now):
        """The daemon acknowledged the start, or the printer's report named the file: from
        here the printer's reports lead. A second word of the same changes nothing."""
        self.gate_passed = True
        if self.stage in FOLLOWING:
            return
        self.extras.pop('bytes_sent', None)
        self.extras.pop('bytes_total', None)
        if self.running_since is None:
            self.running_since = now
        self.not_seen_since = None
        self._change(now, state=RUNNING, stage='printing', stage_fraction=0.0)

    def fail(self, now, report):
        self.error = report
        self._change(now, state=FAILED)

    def cancel(self, now):
        self._change(now, state=CANCELLED)

    def outcome_unknown(self, now, why):
        """Stop following a delivery job past the start gate whose word has gone: final
        `failed`, with a report that says the outcome is not known (never that the print
        failed)."""
        age = int(self.stale_age) if self.stale_age is not None else 0
        self.fail(now, errors.report_for_code(
            'delivery.outcome_unknown',
            detail=f'{why}; last stage {self.stage}; no fresh word for {age} s'))

    def printer_word(self, snapshot):
        """What the sync's snapshot says of the printer itself: whether it is reachable,
        and how old its own report is (`report_age_s`, measured by the daemon from the
        last document the printer sent)."""
        self.printer_quiet_s = _number(snapshot.get('report_age_s'))
        self.printer_unreachable = snapshot.get('state') == 'unreachable'
        self.printer_unrecognised = snapshot.get('state') == UNRECOGNISED_STATE

    def print_report(self, snapshot, now):
        """The printer's snapshot while this job prints."""
        if self.final or self.stage not in FOLLOWING:
            return
        state = snapshot.get('state')
        if self.printer_unreachable:
            return                                    # the stale marker tells it, at once
        if self.printer_unrecognised:
            # The printer's main state is one this version does not know: whether the
            # print goes on cannot be told. Never an end and never a vanish; the report
            # keeps its last figures, names the value, and is marked stale, so the caller
            # can stop following it.
            self._change(now, extras={'unrecognised': snapshot.get('unrecognised')
                                      or f'state {state!r}'})
            return
        if not self.printer_has_it(snapshot):
            # Another file, no file, or the printer idle with ours still named: the print
            # is not under way. Counted only while the printer reports.
            if self.not_seen_since is None:
                self.not_seen_since = now
            elif now - self.not_seen_since >= PRINT_VANISH_SECONDS:
                self.fail(now, errors.report_for_code(
                    'delivery.print_vanished',
                    detail=f"printer reports state {state!r}, file "
                           f"{snapshot.get('job_name') or snapshot.get('file')!r}"))
            return
        self.not_seen_since = None
        extras = {
            'printer_stage': snapshot.get('stage'),
            'printer_stage_label': snapshot.get('stage_label'),
            'percent': _number(snapshot.get('percent')),
            'layer': _number(snapshot.get('layer')),
            'total_layers': _number(snapshot.get('layers')) or None,
            'remaining_min': _number(snapshot.get('remaining_min')),
        }
        if state == 'finished':
            self.extras.update(extras)
            self._change(now, state=DONE, stage_fraction=1.0)
            return
        if state == 'error':
            code = snapshot.get('error') or ''
            detail = (f"printer error {code or 'with no code'}; stage "
                      f"{snapshot.get('stage_code')!r}; {snapshot.get('percent')!r} percent")
            if code in errors.PRINTER_STOP_CODES:
                self.fail(now, errors.report_for_code('delivery.print_stopped', detail=detail))
            else:
                self.fail(now, errors.report_for_code(
                    'delivery.print_failed', detail=detail, meaning=errors.meaning_of(code)))
            return
        # Running, or paused: the printer waits for a person (a pause, an error code set
        # while the print is under way, a door open, filament run out). Never an end: the
        # stage says so, with what to do at the printer, and returns to printing when the
        # print resumes.
        waiting = state == 'paused'
        code = (snapshot.get('error') or None) if waiting else None
        extras.update({
            'waiting_for': snapshot.get('waiting_for') or 'paused' if waiting else None,
            'waiting_label': (snapshot.get('waiting_label') or snapshot.get('stage_label')
                              or 'Paused') if waiting else None,
            'at_the_printer': (snapshot.get('at_the_printer') or AT_THE_PRINTER)
            if waiting else None,
            'printer_error': code,
            'printer_error_meaning': errors.PRINTER_ERROR_MEANINGS.get(code) if code else None,
            'unrecognised': snapshot.get('unrecognised') or None,
        })
        percent = extras['percent']
        self._change(now, stage='waiting_for_person' if waiting else 'printing',
                     stage_fraction=None if percent is None else percent / 100.0,
                     extras=extras)

    def _stale_age(self, now):
        """How old the last word is, when it is too old to show as fresh; else None.

        The daemon silent for STALE_AFTER_SECONDS; during the print, the printer
        unreachable (at once) or its own report unchanged for PRINTER_QUIET_SECONDS. The
        age is the printer's, measured by the daemon from the last document it received,
        plus the time since the daemon last spoke."""
        silent = now - self.last_word_at
        if self.state == RUNNING and silent >= STALE_AFTER_SECONDS:
            return silent
        if self.stage == 'starting' or self.stage in FOLLOWING:
            quiet = self.printer_quiet_s or 0
            if (self.printer_unreachable or self.printer_unrecognised
                    or quiet >= PRINTER_QUIET_SECONDS):
                return quiet + silent
        return None

    def refresh(self, now):
        """Apply the lazy rule, staleness. Returns True on a new report.

        Silence never ends a delivery job: a print may run while the link or the printer
        is quiet, and when word returns the report goes on from it. Only evidence that the
        print has ended ends one (the printer's own report, the daemon's acknowledgement, or
        a start gate that was never passed). The one exception: past the gate, a day with
        no fresh word at all, when the relay stops following it (`delivery.outcome_unknown`,
        which says the outcome is not known)."""
        if self.final:
            return False
        self.stale_age = self._stale_age(now)
        if self.stale_age is None:
            self.fresh_at = now
        elif self.gate_passed and now - self.fresh_at >= OUTCOME_UNKNOWN_AFTER_SECONDS:
            self.outcome_unknown(now, f'the relay stopped following it after '
                                      f'{OUTCOME_UNKNOWN_AFTER_SECONDS // 3600} h')
            return True
        if (self.stale_age is not None) != bool(self.report.get('stale')):
            self._emit(now)
            return True
        if self.stale_age is not None:
            self.report = dict(self.report, stale_age_s=int(self.stale_age))
        return False
