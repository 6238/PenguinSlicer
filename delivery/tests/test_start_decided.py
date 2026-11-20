"""How a start is decided (the guide's section of that name), on the whole path: the relay
app, the real run loop and relay client, the stand-in printer, fake clocks. Review 4's
defects 1 to 4 and the reviewer's sequences, then random sequences of the same faults
with the invariants: one start command per file, no two files overlapping on the printer,
nothing after a final state, no end taken from a picture that does not show it."""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_relay import deliveries as dl

from link_faults import BASE, DaemonDied, Shop
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
        if self.pending or printer._snapshot['state'] in ('running', 'paused'):
            self.overlaps.append((remote_name, self.pending, dict(printer._snapshot)))
        before = dict(printer._snapshot)
        accepted = self._start(remote_name)
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


# --- random sequences --------------------------------------------------------------------

#: The settings of "How a start is decided", scaled down for the random sequences so each
#: runs in a fraction of a second. The rules compare times with one another, never with a
#: figure of their own, so the invariants hold at any scale.
SCALED = {'START_SLOW_SECONDS': 10.0, 'START_SETTLE_SECONDS': 60.0,
          'LEFTOVER_END_SECONDS': 15.0, 'PRINTER_WAIT_SECONDS': 120.0}
END_STATE = {'finished': 'finished', 'error': 'error', 'idle_error': 'error'}


@settings(max_examples=40, deadline=None, derandomize=True, database=None,
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
       restart_at=st.one_of(st.none(), st.integers(1, 80)))
def test_random_starts_never_overlap_and_never_end_on_a_left_over(
        tmp_path_factory, show_after, previous_end, linger, partial, quiet, outages,
        stop_at, resend_at, restart_at):
    """The printer before the send is idle or shows the previous print's end; after a
    start command it may keep that end with our name on it (`linger`, a left-over) and
    show the print `show_after` seconds later, or never. Partial pictures, quiet streams,
    outages, a stop-following, a resend and a daemon restart land at random moments."""
    with pytest.MonkeyPatch.context() as patch:
        for name, value in SCALED.items():
            patch.setattr(rl, name, value)
        # The relay marks a quiet printer stale on the same scale, so a caller can stop
        # following a job inside the hold and send again.
        patch.setattr(dl, 'PRINTER_QUIET_SECONDS', 10)
        random_starts(tmp_path_factory.mktemp('shop'), show_after, previous_end, linger,
                      partial, quiet, outages, stop_at, resend_at, restart_at)


@settings(max_examples=30, deadline=None, derandomize=True, database=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture,
                                 HealthCheck.too_slow])
@given(show_after=st.integers(25, 54),
       previous_end=st.sampled_from([None, 'finished', 'error']),
       linger=st.booleans(),
       quiet_at=st.integers(0, 6), quiet_for=st.integers(12, 20),
       stop_after=st.integers(11, 12), resend_after=st.integers(0, 2),
       restart_at=st.one_of(st.none(), st.integers(1, 60)))
def test_a_resend_while_the_first_start_is_unsettled_never_overlaps(
        tmp_path_factory, show_after, previous_end, linger, quiet_at, quiet_for,
        stop_after, resend_after, restart_at):
    """The sequence ruling 4 is about, aimed at: the printer goes quiet just after the
    start command (its last document without the print), the caller stops following once
    the relay marks it stale and sends again at once, the printer answers again without
    the print, and shows the first print later, inside the stated time. Without the hold,
    the second start command would go while the first is still pending."""
    stop_at = quiet_at + stop_after + 10
    with pytest.MonkeyPatch.context() as patch:
        for name, value in SCALED.items():
            patch.setattr(rl, name, value)
        patch.setattr(dl, 'PRINTER_QUIET_SECONDS', 10)
        random_starts(tmp_path_factory.mktemp('shop'), show_after, previous_end, linger,
                      [], [(quiet_at + 10, quiet_for)], [], stop_at,
                      stop_at + resend_after, restart_at)


def random_starts(tmp_path, show_after, previous_end, linger, partial, quiet, outages,
                  stop_at, resend_at, restart_at):
    shop = Shop(tmp_path)
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
    real_read = shop.printer._read
    spells = {'partial': 0}

    def read():
        snap = real_read()
        return dict(snap, whole=False) if spells['partial'] else snap

    shop.printer._read = read
    shop.online()
    jobs = [shop.send()]
    for at, length in partial:
        shop.at(at, lambda: spells.update(partial=spells['partial'] + 1))
        shop.at(at + length, lambda: spells.update(partial=spells['partial'] - 1))
    for at, length in quiet:
        shop.printer.quiet(shop, at, length)
    for at, length in outages:
        shop.printer.outage(shop, at, length)
    if stop_at is not None:
        shop.at(stop_at, lambda: stop_following(shop, jobs[0]))
    if resend_at is not None:
        def again():
            status, job_id, _code = resend(shop)
            resent['done'] = True
            if status == 202:
                jobs.append(job_id)
        shop.at(resend_at, again)

    def die():
        raise DaemonDied()

    if restart_at is not None:
        shop.at(restart_at, die)
    for _step in range(3600):
        # A second at a time while a job is live; five while all is quiet until the resend.
        settled = all(shop.final(job_id) for job_id in jobs)
        if settled and resent['done']:
            break
        try:
            shop.advance(5 if settled else 1)
            shop.tick()
        except DaemonDied:
            shop.restart_daemon()
    # A printer slower to show the print than START_SETTLE_SECONDS is past the stated
    # time: the daemon then rightly takes it not to have started the file (or, blind, a
    # left-over end for this print's), and a printer that starts after that can overlap.
    # Every other sequence must not.
    slow = show_after is None or show_after >= rl.START_SETTLE_SECONDS - 5
    # One start command per file; no start while the printer prints or holds another.
    assert len(shop.printer.started) == len(set(shop.printer.started))
    if not (show_after is not None and slow):
        assert model.overlaps == [], model.overlaps
    for evidence in shop.printer.start_evidence:
        assert evidence['state'] in ('idle', 'finished', 'error'), evidence
        assert evidence.get('whole') is not False, evidence
        assert evidence['report_age_s'] <= rl.FRESH_REPORT_SECONDS, evidence
    # A daemon that could not watch continuously (restarted, or without a whole, fresh
    # picture for a while) takes a left-over end for ours once the command is
    # START_SETTLE_SECONDS old: a real end must be found, not waited on for ever.
    blind = restart_at is not None or any(
        length >= rl.LEFTOVER_END_SECONDS for _at, length in partial + quiet + outages)
    # The left-over a blind daemon may take: the end the printer showed at a start command.
    blind_end = (('finished', 'error') if (blind and slow and lingering) else ())
    for job_id in jobs:
        report = shop.report(job_id)
        assert report is not None
        code = (report.get('error') or {}).get('code')
        name = f'sample_part-{job_id}.gcode.3mf'
        if report['state'] == 'done':
            assert name in model.showed or 'finished' in blind_end, \
                ('done, but the printer never showed the print', report)
        # No real printer error was injected: an end of that kind would be a left-over.
        if code in ('delivery.printer_error_at_start', 'delivery.print_failed',
                    'delivery.print_stopped'):
            assert 'error' in blind_end, report
        if code in ('delivery.start_timeout', 'delivery.start_other_file'):
            assert name not in model.showed or slow, report
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
