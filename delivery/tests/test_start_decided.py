"""How a start is decided (the guide's section of that name), on the whole path: the relay
app, the real run loop and relay client, the stand-in printer, fake clocks. Review 4's
defects 1 to 4 and the reviewer's sequences, then random sequences of the same faults
with the invariants: one start command per file, no two files overlapping on the printer,
nothing after a final state, no end taken from a picture that does not show it."""

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_relay import deliveries as dl

from link_faults import BASE, DaemonDied, Shop, check_start_path
from test_link_faults import assert_no_tight_loop, assert_truthful

PREVIOUS = 'previous_part-j00000001'


class PrinterModel:
    """What the stand-in printer does with a start command, beyond showing it at once.

    `show_after` seconds of the picture it had (idle, or `lingering`: the previous print's
    end with our name already on it) before it shows the print running; None, it never
    starts the file. `pending` is the printer's own truth: it accepted a start and has not
    begun it. A start command that reaches the printer while it prints or while an earlier
    start is pending is an overlap, recorded in `overlaps`."""

    def __init__(self, shop, *, show_after=0, lingering=None, print_seconds=600):
        self.shop = shop
        self.show_after = show_after
        self.lingering = lingering
        self.pending = False
        self.showed = []
        self.overlaps = []
        printer = shop.printer
        printer.print_seconds = print_seconds
        self._start = printer.start
        printer.start = self.start

    def start(self, remote_name):
        printer = self.shop.printer
        if printer.start_raises == 'before':
            return self._start(remote_name)             # raises: it never reaches the printer
        if self.pending or printer.truth()['state'] in ('running', 'paused'):
            self.overlaps.append((remote_name, self.pending, dict(printer._snapshot)))
        before = dict(printer._snapshot)
        reached = len(printer.started)
        raised = None
        try:
            accepted = self._start(remote_name)
        except OSError as e:
            if len(printer.started) == reached:
                raise                                   # it never reached the printer
            raised, accepted = e, True                  # reached it, and the answer was lost
        try:
            return self._after_start(remote_name, accepted, before)
        finally:
            if raised is not None:
                raise raised

    def _after_start(self, remote_name, accepted, before):
        printer = self.shop.printer
        if not accepted or self.show_after == 0:
            if accepted:
                self.showed.append(remote_name)
            return accepted
        running = dict(printer._snapshot)
        if self.lingering == 'previous':
            # The printer's own state at the command, kept, with our name put on it: a
            # left-over end when it showed one, else simply the idle printer.
            if before['state'] in ('finished', 'error'):
                printer._snapshot = dict(before, file=running['file'],
                                         job_name=running['job_name'])
            else:
                printer._snapshot = printer._idle()
        elif self.lingering == 'finished':
            printer._snapshot = dict(running, state='finished', percent=100)
        elif self.lingering == 'error':
            printer._snapshot = dict(running, state='error', error='PRINT_ERROR_0300400C')
        elif self.lingering == 'idle_error':
            printer._snapshot = dict(running, state='error', stage_code=255, stage='idle',
                                     error='PRINT_ERROR_0300400C')
        else:
            printer._snapshot = printer._idle()
        printer.started_at = None
        if self.show_after is None:
            return accepted
        self.pending = True

        def show():
            self.pending = False
            printer._snapshot = running
            printer.started_at = printer.clock()
            self.showed.append(remote_name)

        self.shop.at(self.show_after, show)
        return accepted


def resend(shop):
    resp = shop.pages.post('/printer/jobs', json={'token': 'tok'}, base_url=BASE)
    body = resp.get_json()
    return resp.status_code, body.get('job_id'), (body.get('error_report') or {}).get('code')


def stop_following(shop, job_id):
    resp = shop.pages.post(f'/printer/jobs/{job_id}/stop-following', base_url=BASE)
    return resp.status_code, (resp.get_json().get('error_report') or {}).get('code')


def cancel(shop, job_id):
    resp = shop.pages.post(f'/printer/jobs/{job_id}/cancel', base_url=BASE)
    report = resp.get_json().get('error_report') or {}
    return resp.status_code, report.get('code'), report.get('message')


# --- defect 1: a picture with no main state is never free --------------------------------

def test_a_document_with_no_main_state_during_another_print_starts_nothing(tmp_path):
    """The reviewer's H2: the daemon hears only a document with no main state while
    someone else's print runs (figures and a name). The relay refuses the send as not
    recognised, and nothing is started."""
    shop = Shop(tmp_path)
    shop.online()
    partial = pr.map_status({'mc_percent': 43, 'mc_remaining_time': 12, 'layer_num': 5,
                             'subtask_name': 'someone_elses_print'},
                            printer=shop.printer._snapshot['printer'])
    shop.printer._snapshot = partial
    shop.drive(10)
    assert resend(shop)[0] == 409
    assert shop.printer.started == []


def test_a_picture_not_whole_since_the_reconnect_starts_nothing_until_a_whole_one(tmp_path):
    """The daemon reconnected; the library still holds the last connection's IDLE and
    only partial documents have come since (`whole: False`) while someone else's print
    runs. The relay accepts the send on the old idle picture; the daemon does not trust
    it, asks for a whole report and waits; the whole report shows the other print."""
    shop = Shop(tmp_path)
    shop.online()
    real_read = shop.printer._read
    whole = {'now': False}
    asked = []
    shop.printer.request_report = lambda: asked.append(shop())

    def read():
        snap = real_read()
        if not whole['now']:
            return dict(snap, whole=False)
        return dict(snap, state='running', file='someone_elses_print',
                    job_name='someone_elses_print', percent=43)

    shop.printer._read = read
    job_id = shop.send()
    shop.at(40, lambda: whole.update(now=True))
    assert shop.drive(300, lambda: shop.final(job_id))
    report = shop.report(job_id)
    assert report['error']['code'] == 'delivery.printer_busy_at_start'
    assert shop.printer.started == [] and asked
    assert_truthful(shop, job_id)


# --- defect 2: an end counts only if it is the end of this print -------------------------

@pytest.mark.parametrize('lingering', ['finished', 'error', 'idle_error'])
@pytest.mark.parametrize('show_after', [6, 90])
def test_a_left_over_end_with_our_name_never_ends_the_job(tmp_path, lingering, show_after):
    """The reviewer's H3: after the start command the printer names our file under the
    previous print's end (`FINISH`, `FAILED`, idle with an error code) for a while, then
    runs it. The job stays in progress, then follows the print to its real end."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=show_after, lingering=lingering, print_seconds=300)
    shop.online()
    job_id = shop.send()
    seen = []
    shop.at(show_after + 40, lambda: seen.append(shop.report(job_id)))
    assert shop.drive(3600, lambda: shop.final(job_id))
    assert seen[0]['state'] == 'running'
    assert seen[0]['stage'] in ('starting', 'start_not_shown', 'printing')
    report = shop.report(job_id)
    assert report['state'] == 'done'
    assert model.showed == shop.printer.started and model.overlaps == []
    assert_truthful(shop, job_id)


def test_a_left_over_end_that_stays_is_a_start_the_printer_ignored(tmp_path):
    """The previous print's FINISH, before the start and after it, with our name put on it
    and never anything else: the state never changed, so it is not our end. After
    START_SETTLE_SECONDS the job ends `delivery.start_timeout`, never `done`."""
    shop = Shop(tmp_path)
    shop.printer._snapshot = dict(shop.printer._idle(), state='finished', file=PREVIOUS,
                                  job_name=PREVIOUS, percent=100)
    PrinterModel(shop, show_after=None, lingering='finished')
    shop.online()
    job_id = shop.send()
    assert shop.drive(1800, lambda: shop.final(job_id))
    report = shop.report(job_id)
    assert report['error']['code'] == 'delivery.start_timeout'
    assert len(shop.printer.started) == 1
    assert_truthful(shop, job_id)


def test_a_daemon_restarted_just_after_the_start_waits_for_the_print(tmp_path):
    """The daemon dies right after the start command, under a left-over end with our name;
    the restarted daemon rebuilds the hold from the relay's gate age and never takes that
    end for ours; the print shows and the job follows it to `done`."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=40, lingering='finished', print_seconds=200)
    shop.online()

    def die():
        raise DaemonDied()

    original = model.start

    def start_then_die(name):
        accepted = original(name)
        shop.at(1, die)
        return accepted

    shop.printer.start = start_then_die
    job_id = shop.send()
    for _ in range(3600):
        try:
            shop.advance(1)
            shop.tick()
        except DaemonDied:
            shop.restart_daemon()
        if shop.final(job_id):
            break
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1 and model.overlaps == []
    assert_truthful(shop, job_id)


# --- defect 3: every wait before the gate ------------------------------------------------

def test_a_printer_quiet_from_the_download_on_can_be_cancelled(tmp_path):
    """The reviewer's H4: the printer goes quiet at the download and the first asks of the
    start gate time out. The job waits before the gate (`waiting_for_printer`), a cancel
    works, and nothing is ever started or said to have started."""
    shop = Shop(tmp_path)
    shop.online()
    shop.link.before['download'] = lambda: shop.printer.quiet(shop, 0, 400)
    shop.link.inject('start', 'timeout', 'timeout', 'timeout')
    job_id = shop.send()
    seen = {}

    def look_then_cancel():
        seen['report'] = shop.report(job_id)
        seen['cancel'] = cancel(shop, job_id)

    shop.at(60, look_then_cancel)
    assert shop.drive(1200, lambda: shop.final(job_id))
    assert seen['report']['stage'] == 'waiting_for_printer'
    assert seen['cancel'][0] == 202
    assert shop.report(job_id)['state'] == 'cancelled'
    assert shop.printer.started == []
    assert_truthful(shop, job_id)


# --- defect 4: the printer is held after a start command ---------------------------------

def test_a_printer_slow_to_show_the_print_is_not_failed_and_gets_no_second_start(tmp_path):
    """The reviewer's H6: the printer takes 90 s of fresh idle reports to show the print.
    At 80 s the job is in progress (`start_not_shown`, the time waited); a resend is
    refused; the job ends `done`; one start command."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=90, print_seconds=300)
    shop.online()
    job_id = shop.send()
    seen = {}

    def look():
        seen['report'] = shop.report(job_id)
        seen['resend'] = resend(shop)

    shop.at(80, look)
    assert shop.drive(3600, lambda: shop.final(job_id))
    assert (seen['report']['state'], seen['report']['stage']) == ('running',
                                                                 'start_not_shown')
    assert seen['report']['waited_s'] >= rl.START_SLOW_SECONDS
    assert seen['resend'][0] == 409
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1 and model.overlaps == []


def test_stop_following_then_a_resend_waits_for_the_earlier_start(tmp_path):
    """The printer is quiet for 150 s after the start (its last document the idle one),
    then answers idle, and shows the first print only at 250 s. At 120 s the caller stops
    following the first job and sends again. The second job waits in
    `waiting_for_earlier_print` and is refused as busy once the first print shows: no
    second start command, ever."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=250, print_seconds=3600)
    shop.online()
    first = shop.send()
    original = model.start

    def start_then_quiet(name):
        accepted = original(name)
        if len(shop.printer.started) == 1:
            shop.printer.quiet(shop, 0, 150)
            shop.printer.frozen = dict(shop.printer._idle())
        return accepted

    shop.printer.start = start_then_quiet
    seen = {}

    def give_up_and_resend():
        seen['stop'] = stop_following(shop, first)
        seen['send'] = resend(shop)

    shop.at(120, give_up_and_resend)
    shop.at(200, lambda: seen.update(stage=shop.report(seen['send'][1])['stage']))
    assert shop.drive(1800, lambda: 'send' in seen and shop.final(seen['send'][1]))
    assert seen['stop'] == (200, None)
    assert seen['send'][0] == 202
    assert seen['stage'] == 'waiting_for_earlier_print'
    second = shop.report(seen['send'][1])
    assert second['error']['code'] == 'delivery.printer_busy_at_start'
    assert len(shop.printer.started) == 1 and model.overlaps == []
    assert_truthful(shop, seen['send'][1])


def test_a_start_the_printer_ignored_frees_the_printer_only_after_it_settles(tmp_path):
    """Nothing ever happens after the start command. Stop-following is refused while the
    printer answers (`delivery.start_not_shown_yet`); the job ends `delivery.start_timeout`
    after START_SETTLE_SECONDS; a resend is then accepted and started."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=None)
    shop.online()
    job_id = shop.send()
    seen = {}
    shop.at(120, lambda: seen.update(stop=stop_following(shop, job_id)))
    assert shop.drive(1800, lambda: shop.final(job_id))
    assert seen['stop'] == (409, 'delivery.start_not_shown_yet')
    report = shop.report(job_id)
    assert report['error']['code'] == 'delivery.start_timeout'
    assert report['elapsed_s'] >= rl.START_SETTLE_SECONDS
    model.show_after = 0
    status, second, _code = resend(shop)
    assert status == 202
    assert shop.drive(1800, lambda: shop.final(second))
    assert shop.report(second)['state'] == 'done'
    assert len(shop.printer.started) == 2 and model.overlaps == []


# --- review 5, defects 3 and 4: restarts between the gate and the settling ---------------

#: The points between the gate and the settling where a half restarts: after the gate's
#: yes and before the note; after the note and before the command; after the command and
#: before the note says it went; after that; 30 s into the hold; at the acknowledgement
#: once the print has shown.
POINTS = ('gate', 'noted', 'sent', 'marked', 'held', 'settled')
#: What a cancel 90 s after a daemon-only restart must answer: the command may not have
#: gone until the note says it did.
CANCEL_AFTER_DAEMON_RESTART = {
    'gate': 'delivery.start_being_sent', 'noted': 'delivery.start_being_sent',
    'sent': 'delivery.start_being_sent', 'marked': 'delivery.cancel_too_late',
    'held': 'delivery.cancel_too_late', 'settled': 'delivery.already_finished'}


def drive_with_deaths(shop, seconds, until):
    """Drive the shop, starting a new daemon process whenever one dies, wherever it was."""
    for _ in range(seconds):
        if until():
            return True
        try:
            shop.advance(1)
            shop.tick()
        except DaemonDied:
            shop.restart_daemon()
    return until()


@pytest.mark.parametrize('half', ['daemon', 'relay', 'both'])
@pytest.mark.parametrize('point', POINTS)
def test_a_restart_between_the_gate_and_the_settling_never_sends_a_second_start(
        tmp_path, monkeypatch, half, point):
    """The printer shows a print 200 s after a start command reaches it. One half, or
    both, restart at `point`; 70 s later the caller sends again, and 90 s later cancels
    the first job. At most one start command reaches the printer while it holds another,
    each file is sent one start command at most, a cancel never says a command went that
    may not have, and once all is over the printer is free for the next send."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=200, print_seconds=60)
    shop.online()
    seen = {}
    jobs = []

    def event():
        if seen.get('event_at') is not None:
            return
        seen['event_at'] = shop()
        seen['commands_at_event'] = len(shop.printer.started)
        if half in ('relay', 'both'):
            shop.restart_relay()
            shop.status()
        shop.at(70, again)
        shop.at(90, lambda: seen.update(cancel=cancel(shop, jobs[0])))
        if half in ('daemon', 'both'):
            raise DaemonDied()

    def again():
        status, job_id, _code = resend(shop)
        seen['resend'] = status
        if status == 202:
            jobs.append(job_id)

    real_save = rl.start_record.save

    def save(path, **fields):
        if point == 'gate' and fields['phase'] == 'sending':
            event()
        if point == 'sent' and fields['phase'] == 'sent':
            event()
        real_save(path, **fields)
        if point == 'noted' and fields['phase'] == 'sending':
            event()
        if point == 'marked' and fields['phase'] == 'sent':
            event()
        if point == 'held' and fields['phase'] == 'sent':
            shop.at(30, event)

    monkeypatch.setattr(rl.start_record, 'save', save)
    if point == 'settled':
        def at_the_ack():
            if model.showed:
                event()
            else:
                shop.link.before['ack'] = at_the_ack
        shop.link.before['ack'] = at_the_ack
    jobs.append(shop.send())
    assert drive_with_deaths(shop, 3600, lambda: 'resend' in seen and all(
        shop.report(job_id) is None or shop.final(job_id) for job_id in jobs))
    # One start command per file; none while the printer printed or held another.
    assert len(shop.printer.started) == len(set(shop.printer.started))
    assert model.overlaps == [], model.overlaps
    sent_first = seen['commands_at_event'] == 1 or point not in ('gate', 'noted')
    if half == 'daemon':
        assert seen['cancel'][1] == CANCEL_AFTER_DAEMON_RESTART[point], seen['cancel']
        first = shop.report(jobs[0])
        if sent_first:
            assert first['state'] == 'done', first
        else:
            assert first['error']['code'] == 'delivery.start_timeout', first
            assert shop.printer.started == [] or len(jobs) > 1
    else:
        assert seen['cancel'][1] == 'delivery.job_unknown', seen['cancel']
    # The printer is not blocked: once its own print is over, a send prints. (A relay
    # that restarted no longer knows the first job, so its print may still be going.)
    assert drive_with_deaths(shop, 1800, lambda: not model.pending and
                             shop.printer._snapshot['state'] not in ('running', 'paused'))
    shop.drive(10)
    model.show_after = 0
    status, last, code = resend(shop)
    assert status == 202, (code, shop.status())
    assert drive_with_deaths(shop, 1800, lambda: shop.final(last))
    assert shop.report(last)['state'] == 'done'
    assert model.overlaps == []


def test_both_halves_restarted_inside_the_hold_keep_the_printer_held(tmp_path):
    """The reviewer's sequence (review 5, defect 3): start command at once, the printer
    shows the print 200 s later; the daemon and the relay both restart at 40 s; the
    resend at 70 s is accepted by the new relay, waits behind the note's hold, and is
    refused once the first print shows. One start command."""
    shop = Shop(tmp_path)
    model = PrinterModel(shop, show_after=200, print_seconds=600)
    shop.online()
    shop.send()
    seen = {}

    def both():
        shop.restart_relay()
        shop.status()
        raise DaemonDied()

    def again():
        seen['resend'] = resend(shop)

    shop.at(40, both)
    shop.at(70, again)
    shop.at(150, lambda: seen.update(stage=shop.report(seen['resend'][1])['stage']))
    assert drive_with_deaths(shop, 1200, lambda: 'stage' in seen
                             and shop.final(seen['resend'][1]))
    assert seen['resend'][0] == 202
    assert seen['stage'] == 'waiting_for_earlier_print'
    assert shop.report(seen['resend'][1])['error']['code'] == 'delivery.printer_busy_at_start'
    assert len(shop.printer.started) == 1 and model.overlaps == []


def test_a_daemon_dead_between_the_gate_and_the_command_is_never_said_to_have_sent_it(
        tmp_path):
    """The reviewer's sequence (review 5, defect 4): the daemon dies after the gate and
    before the start command. Cancels at 20 s and 90 s both answer
    `delivery.start_being_sent` ("may already have sent"), never
    `delivery.cancel_too_late`; the job ends `delivery.start_timeout`; nothing was sent."""
    shop = Shop(tmp_path)
    PrinterModel(shop, show_after=0)
    shop.online()
    original = shop.printer.start
    seen = {}

    def die_first(name):
        shop.printer.start = original
        shop.at(20, lambda: seen.update(cancel_20=cancel(shop, first)))
        shop.at(90, lambda: seen.update(cancel_90=cancel(shop, first),
                                        stage_90=shop.report(first)['stage']))
        raise DaemonDied()

    shop.printer.start = die_first
    first = shop.send()
    assert drive_with_deaths(shop, 900, lambda: shop.final(first))
    assert seen['cancel_20'][:2] == (409, 'delivery.start_being_sent')
    assert seen['cancel_90'][:2] == (409, 'delivery.start_being_sent')
    assert 'may already have sent' in seen['cancel_90'][2]
    assert seen['stage_90'] == 'start_not_shown'
    assert shop.report(first)['error']['code'] == 'delivery.start_timeout'
    assert shop.printer.started == []
    assert_truthful(shop, first)


def test_a_note_that_cannot_be_written_reaches_the_caller_as_not_started(tmp_path):
    """The daemon cannot write its note of the start: no start command, the file is
    removed, and the caller's error report says the print was not started."""
    shop = Shop(tmp_path)
    (tmp_path / 'start.json').mkdir()
    (tmp_path / 'start.json' / 'in-the-way').write_text('x')
    shop.restart_daemon()                  # a new process that reads the unreadable note
    shop.loops[0].hold = None              # (a damaged note holds; here only the write is tried)
    shop.online()
    job_id = shop.send()
    assert shop.drive(600, lambda: shop.final(job_id))
    report = shop.report(job_id)
    assert report['error']['code'] == 'delivery.start_not_recorded'
    assert 'did not start the print' in report['error']['message']
    assert report['error']['retryable'] is True
    assert shop.printer.started == []
    assert_truthful(shop, job_id)


# --- random sequences --------------------------------------------------------------------

#: The settings of "How a start is decided", scaled down for the random sequences so each
#: runs in a fraction of a second. The rules compare times with one another, never with a
#: figure of their own, so the invariants hold at any scale.
SCALED = {'START_SLOW_SECONDS': 10.0, 'START_SETTLE_SECONDS': 60.0,
          'LEFTOVER_END_SECONDS': 15.0, 'PRINTER_WAIT_SECONDS': 120.0}
END_STATE = {'finished': 'finished', 'error': 'error', 'idle_error': 'error'}


#: Where a daemon may die on the way to the start command, for the random sequences:
#: after the gate and before the note, after the note and before the command, after the
#: command and before the note says it went.
DEATHS = (None, 'gate', 'noted', 'sent')
#: A start command that raises: before it reaches the printer, or after.
START_FAULTS = (None, 'before', 'after')


@settings(max_examples=80, deadline=None, derandomize=True, database=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture,
                                 HealthCheck.too_slow])
@given(show_after=st.one_of(st.none(), st.integers(0, 60)),
       previous_end=st.sampled_from([None, 'finished', 'error', 'idle_error']),
       linger=st.booleans(),
       partial=st.lists(st.tuples(st.integers(0, 80), st.integers(1, 30)), max_size=2),
       quiet=st.lists(st.tuples(st.integers(0, 80), st.integers(1, 60)), max_size=2),
       outages=st.lists(st.tuples(st.integers(0, 80), st.integers(1, 40)), max_size=2),
       stop_at=st.one_of(st.none(), st.integers(1, 120)),
       resend_at=st.one_of(st.none(), st.integers(1, 150)),
       restart_at=st.one_of(st.none(), st.integers(1, 80)),
       whole_after=st.integers(0, 40),
       someone=st.one_of(st.none(), st.tuples(st.one_of(st.just(0), st.integers(0, 80)),
                                              st.integers(1, 60))),
       cancel_at=st.one_of(st.none(), st.none(), st.none(), st.integers(1, 60)),
       death=st.one_of(st.none(), st.sampled_from(DEATHS[1:])),
       start_fault=st.one_of(st.none(), st.sampled_from(START_FAULTS[1:])),
       relay_restart_at=st.one_of(st.none(), st.none(), st.none(), st.integers(1, 80)))
def test_random_starts_never_overlap_and_never_end_on_a_left_over(
        tmp_path_factory, show_after, previous_end, linger, partial, quiet, outages,
        stop_at, resend_at, restart_at, whole_after, someone, cancel_at, death,
        start_fault, relay_restart_at):
    """The printer before the send is idle or shows the previous print's end; after a
    start command it may keep that end with our name on it (`linger`, a left-over) and
    show the print `show_after` seconds later, or never. The daemon hears it through the
    real PrinterLink: each connection has only partial documents for `whole_after`
    seconds, and `partial` spells are reconnects. Quiet streams, outages (during one of
    which someone may start a print at the printer), a stop-following, a cancel, a resend,
    a daemon dying anywhere or on the way to the start command, a start command that
    raises, and a relay restart land at random moments."""
    with pytest.MonkeyPatch.context() as patch:
        for name, value in SCALED.items():
            patch.setattr(rl, name, value)
        # The relay marks a quiet printer stale on the same scale, so a caller can stop
        # following a job inside the hold and send again.
        patch.setattr(dl, 'PRINTER_QUIET_SECONDS', 10)
        random_starts(tmp_path_factory.mktemp('shop'), patch, show_after, previous_end,
                      linger, partial, quiet, outages, stop_at, resend_at, restart_at,
                      whole_after=whole_after, someone=someone, cancel_at=cancel_at,
                      death=death, start_fault=start_fault,
                      relay_restart_at=relay_restart_at)


@settings(max_examples=120, deadline=None, derandomize=True, database=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture,
                                 HealthCheck.too_slow])
@given(show_after=st.one_of(st.integers(25, 54), st.integers(45, 54), st.none()),
       previous_end=st.sampled_from([None, 'finished', 'error']),
       linger=st.booleans(),
       quiet_at=st.integers(0, 6), quiet_for=st.integers(12, 20),
       stop_after=st.integers(11, 12), resend_after=st.integers(0, 2),
       restart_at=st.one_of(st.none(), st.integers(1, 60), st.integers(30, 50)),
       whole_after=st.integers(0, 20),
       death=st.sampled_from(DEATHS),
       relay_restart=st.sampled_from([None, 'relay', 'both']), damage_note=st.booleans())
def test_a_resend_while_the_first_start_is_unsettled_never_overlaps(
        tmp_path_factory, show_after, previous_end, linger, quiet_at, quiet_for,
        stop_after, resend_after, restart_at, whole_after, death, relay_restart,
        damage_note):
    """The sequence ruling 4 is about, aimed at: the printer goes quiet just after the
    start command (its last document without the print), the caller stops following once
    the relay marks it stale and sends again at once, the printer answers again without
    the print, and shows the first print later, inside the stated time, or never. Without
    the hold, the second start command would go while the first is still pending, and a
    hold that waits longer than its rule holds the second job back for nothing. The
    daemon may die on the way to the command or at a random moment, and the relay (or the
    relay and the daemon together) may restart just before the resend; a restarted daemon
    may find its note damaged."""
    stop_at = quiet_at + stop_after + 10
    with pytest.MonkeyPatch.context() as patch:
        for name, value in SCALED.items():
            patch.setattr(rl, name, value)
        patch.setattr(dl, 'PRINTER_QUIET_SECONDS', 10)
        random_starts(tmp_path_factory.mktemp('shop'), patch, show_after, previous_end,
                      linger, [], [(quiet_at + 10, quiet_for)], [], stop_at,
                      stop_at + resend_after + (8 if relay_restart else 0), restart_at,
                      whole_after=whole_after, death=death,
                      relay_restart_at=stop_at if relay_restart else None,
                      daemon_dies_with_relay=relay_restart == 'both',
                      damage_note=damage_note)


def random_starts(tmp_path, patch, show_after, previous_end, linger, partial, quiet,
                  outages, stop_at, resend_at, restart_at, *, whole_after=0, someone=None,
                  cancel_at=None, death=None, start_fault=None, relay_restart_at=None,
                  daemon_dies_with_relay=False, damage_note=False):
    shop = Shop(tmp_path, linked=True, whole_after=whole_after)
    if damage_note:
        # The disk loses the note's end while the daemon is down: the next process finds
        # a note it cannot read.
        restart = shop.restart_daemon

        def restart_with_a_damaged_note():
            if os.path.exists(shop.start_record_path):
                with open(shop.start_record_path, 'r+b') as fh:
                    fh.truncate(10)
            restart()

        shop.restart_daemon = restart_with_a_damaged_note
    before = END_STATE.get(previous_end, 'idle')
    if previous_end is not None:
        shop.printer._snapshot = dict(shop.printer._idle(), state=before, file=PREVIOUS,
                                      job_name=PREVIOUS, percent=100)
        if previous_end == 'idle_error':
            shop.printer._snapshot.update(stage_code=255, stage='idle',
                                          error='PRINT_ERROR_0300400C')
    lingering = 'previous' if linger else None
    model = PrinterModel(shop, show_after=show_after, lingering=lingering,
                         print_seconds=30)
    resent = {'done': resend_at is None}
    cancels = []
    shop.online()
    jobs = [shop.send()]
    shop.printer.start_raises = start_fault
    for at, length in partial:
        # A reconnect: the last connection's picture, then only partial documents for
        # `length` seconds.
        shop.at(at, lambda length=length: shop.heard.library.reconnect(length))
    for at, length in quiet:
        shop.printer.quiet(shop, at, length)
    for at, length in outages:
        shop.printer.outage(shop, at, length)
    if someone is not None:
        at, length = someone
        shop.printer.outage(shop, at, 5)
        shop.printer.someone_prints(shop, at + 1, length, pending=lambda: model.pending)
    if stop_at is not None:
        shop.at(stop_at, lambda: stop_following(shop, jobs[0]))
    if cancel_at is not None:
        def cancel_first():
            _status, code, _message = cancel(shop, jobs[0])
            cancels.append((jobs[0], code, shop(), list(shop.printer.commanded)))
        shop.at(cancel_at, cancel_first)
    if resend_at is not None:
        def again():
            status, job_id, _code = resend(shop)
            resent['done'] = True
            if status == 202:
                jobs.append(job_id)
        shop.at(resend_at, again)
    if relay_restart_at is not None:
        def relay_restarts():
            shop.restart_relay()
            shop.status()
            if daemon_dies_with_relay:
                raise DaemonDied()              # both halves restart together
        shop.at(relay_restart_at, relay_restarts)

    def die():
        raise DaemonDied()

    if restart_at is not None:
        shop.at(restart_at, die)
    if death is not None:
        real_save = rl.start_record.save
        dying = {'armed': True}

        def save(path, **fields):
            first = dying['armed'] and fields['phase'] == ('sent' if death == 'sent'
                                                           else 'sending')
            if first and death in ('gate', 'sent'):
                dying['armed'] = False
                raise DaemonDied()
            real_save(path, **fields)
            if first:
                dying['armed'] = False
                raise DaemonDied()

        patch.setattr(rl.start_record, 'save', save)
    def over(job_id):
        # A relay that restarted no longer knows a job it held: over for the caller.
        return shop.final(job_id) or shop.report(job_id) is None

    for _step in range(3600):
        # A second at a time while a job is live; five while all is quiet until the resend.
        settled = all(over(job_id) for job_id in jobs)
        if settled and resent['done']:
            break
        try:
            shop.advance(5 if settled else 1)
            shop.tick()
        except DaemonDied:
            shop.restart_daemon()
        shop.observe(jobs)
    # A printer slower to show the print than START_SETTLE_SECONDS is past the stated
    # time: the daemon then rightly takes it not to have started the file (or, blind, a
    # left-over end for this print's), and a printer that starts after that can overlap.
    # Every other sequence must not.
    slow = show_after is None or show_after >= rl.START_SETTLE_SECONDS - 5
    # No start command while the printer prints or holds another start.
    if not (show_after is not None and slow):
        assert model.overlaps == [], model.overlaps
    # A daemon that could not watch continuously (restarted, or without a whole, fresh
    # picture for a while) takes a left-over end for ours once the command is
    # START_SETTLE_SECONDS old: a real end must be found, not waited on for ever.
    blind = (restart_at is not None or death is not None
             or whole_after >= rl.LEFTOVER_END_SECONDS or any(
                 length >= rl.LEFTOVER_END_SECONDS
                 for _at, length in partial + quiet + outages))
    # The left-over a blind daemon may take: the end the printer showed at a start command.
    blind_end = (('finished', 'error') if (blind and slow and lingering) else ())
    check_start_path(shop, jobs, shown=model.showed, cancels=cancels,
                     exempt_done='finished' in blind_end, exempt_end='error' in blind_end,
                     slow=slow, allow_overlap=show_after is not None and slow,
                     longer_hold=damage_note)
    for job_id in jobs:
        report = shop.report(job_id)
        if report is None:
            assert relay_restart_at is not None
            continue
        if report['state'] == 'running':
            assert report['stage'] in ('printing', 'waiting_for_person', 'starting',
                                       'start_not_shown', 'waiting_for_printer',
                                       'waiting_for_earlier_print'), report
        assert_truthful_job(shop, job_id)
    assert_no_tight_loop(shop, 4200)


def assert_truthful_job(shop, job_id):
    """assert_truthful's report rules for one job of several (it also bounds the starts
    of the whole printer to one, which two jobs may rightly exceed)."""
    final_seen = None
    last_sequence = 0
    for report in shop.reports:
        if report['job'] != job_id:
            continue
        assert report['sequence'] >= last_sequence
        last_sequence = report['sequence']
        if final_seen is not None:
            assert report == final_seen, 'a report after the final one'
        if report['state'] in ('done', 'failed', 'cancelled'):
            final_seen = report
