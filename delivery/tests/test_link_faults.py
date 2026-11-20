"""Hostile cases on the link between the relay and the daemon, each a deterministic
scenario on fake clocks (see link_faults.py), and property-based runs of random faults on
both links.

For every exchange and every fault, the invariants are the brief's: the daemon never
crashes and never busy-loops, a sliced file is started on the printer at most once, the
delivery job ends in the right state (here, done: every injected fault is one a job can
recover from), and the caller's progress reports tell the truth throughout."""
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_relay import relay as relay_module

from penguin_delivery_daemon import printer as pr
from penguin_delivery_relay import deliveries as dl

from link_faults import BASE, CONTENT, DOWNLOAD_FAULTS, EXCHANGES, FAULTS, Canned, DaemonDied, Shop

# Generous for any honest backoff, far below a tight loop (which makes one a tick).
MAX_REQUESTS_PER_SECOND = 1.5


def assert_truthful(shop, job_id):
    """The caller's reports: sequence never goes back, nothing after a final state, and
    the printer started the file at most once."""
    assert not shop.errors
    assert len(shop.printer.started) <= 1, shop.printer.started
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


def assert_no_tight_loop(shop, seconds):
    assert len(shop.link.calls) <= MAX_REQUESTS_PER_SECOND * seconds + 10, len(shop.link.calls)


def deliver_with(shop, exchange, faults, *, seconds=1200):
    shop.link.inject(exchange, *faults)
    shop.online(seconds=300)
    job_id = shop.send()
    finished = shop.drive(seconds, lambda: shop.final(job_id))
    return job_id, finished


@pytest.mark.parametrize('exchange', EXCHANGES)
@pytest.mark.parametrize('fault', FAULTS)
def test_every_exchange_survives_every_fault(tmp_path, exchange, fault):
    shop = Shop(tmp_path)
    job_id, finished = deliver_with(shop, exchange, [fault])
    assert finished, (exchange, fault, shop.report(job_id))
    report = shop.report(job_id)
    assert report['state'] == 'done', report
    assert len(shop.printer.started) == 1
    assert_truthful(shop, job_id)
    assert_no_tight_loop(shop, 1500)


@pytest.mark.parametrize('fault', DOWNLOAD_FAULTS)
def test_a_broken_download_is_caught_and_fetched_again(tmp_path, fault):
    shop = Shop(tmp_path)
    job_id, finished = deliver_with(shop, 'download', [fault])
    assert shop.report(job_id)['state'] == 'done'
    assert list(shop.printer.received.values()) == [CONTENT]   # never the damaged bytes
    assert_truthful(shop, job_id)


@pytest.mark.parametrize('fault', DOWNLOAD_FAULTS)
def test_a_download_broken_every_time_fails_truthfully_and_starts_nothing(tmp_path, fault):
    shop = Shop(tmp_path)
    job_id, finished = deliver_with(shop, 'download', [fault] * 3)
    report = shop.report(job_id)
    assert report['state'] == 'failed'
    expected = 'delivery.download_corrupt' if fault.startswith('wrong') else \
        'delivery.download_failed'
    assert report['error']['code'] == expected
    assert shop.printer.started == []
    assert_truthful(shop, job_id)


@pytest.mark.parametrize('down_for', [5, 90, 900])
def test_the_link_down_for_seconds_or_minutes_then_back_still_delivers(tmp_path, down_for):
    shop = Shop(tmp_path)
    shop.online()
    job_id = shop.send()
    shop.link.down_until = shop() + down_for
    assert shop.drive(down_for + 900, lambda: shop.final(job_id))
    report = shop.report(job_id)
    # Down for longer than the pick-up deadline: the relay says so; else it goes through.
    if down_for > relay_module.JOB_PENDING_TIMEOUT_SECONDS:
        assert report['error']['code'] == 'delivery.job_not_picked_up'
        assert shop.printer.started == []
    else:
        assert report['state'] == 'done'
    assert_truthful(shop, job_id)
    assert_no_tight_loop(shop, down_for + 1200)


def test_the_link_down_for_hours_before_the_gate_never_starts_the_file(tmp_path):
    """Cut while the daemon holds the job and before it asks the gate: the gate is never
    passed, the relay gives the job up at its deadline, and the file is never started."""
    shop = Shop(tmp_path)
    shop.online()
    shop.link.before['start'] = lambda: setattr(shop.link, 'down_until', shop() + 3 * 3600)
    job_id = shop.send()
    shop.drive(3 * 3600 + 600)
    report = shop.report(job_id)
    assert report['state'] == 'failed'
    assert report['error']['code'] == 'delivery.job_not_confirmed'
    assert shop.printer.started == []
    assert shop.printer.received == {}                 # the daemon removed its upload
    assert_truthful(shop, job_id)
    assert_no_tight_loop(shop, 3 * 3600 + 600)


@pytest.mark.parametrize('down_minutes', [17, 60])
def test_the_link_down_from_just_after_the_start_ends_done_not_failed(tmp_path,
                                                                      down_minutes):
    """Defect 1, route B, on the whole path: the start command went out, then the link was
    down past the relay's 15-minute deadline. The print runs meanwhile; the job is stale,
    never failed, and ends done when the link returns."""
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 75 * 60
    shop.online()
    shop.printer.after_start = lambda: setattr(shop.link, 'down_until',
                                               shop() + down_minutes * 60)
    job_id = shop.send()
    shop.drive(300, lambda: shop.printer.started)
    shop.drive(16 * 60)
    report = shop.report(job_id)
    assert (report['state'], report['stale']) == ('running', True), report
    assert shop.drive(2 * 3600, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1
    assert_truthful(shop, job_id)


def test_the_printer_silent_after_an_accepted_start_then_printing_ends_done(tmp_path):
    """Defect 1, route A, on the whole path: the printer accepts the start, cannot be
    reached for 90 s, then reports our file running."""
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 600
    during = []

    def drop_off_for_90_seconds():
        shop.printer.off = True
        shop.at(70, lambda: during.append(shop.report(job_id)))
        shop.at(90, lambda: setattr(shop.printer, 'off', False))

    shop.printer.after_start = drop_off_for_90_seconds
    shop.online()
    job_id = shop.send()
    assert shop.drive(1800, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    # Seventy seconds into the silence: past the daemon's old 60 s give-up, still going,
    # and marked stale rather than showing old figures as fresh. Past START_SLOW_SECONDS
    # the stage says the printer has the file and has not shown the print yet.
    assert (during[0]['state'], during[0]['stage'], during[0]['stale']) == \
        ('running', 'start_not_shown', True)
    assert during[0]['waited_s'] >= 60
    assert len(shop.printer.started) == 1
    assert_truthful(shop, job_id)


def test_the_daemons_failure_sentences_carry_their_figures(tmp_path):
    """Defect 3, on the whole path: the busy printer named with its percent, the
    unreachable printer with its minutes; no "unknown" anywhere."""
    shop = Shop(tmp_path)
    shop.online()
    shop.printer.off = True
    job_id = shop.send()
    assert shop.drive(1200, lambda: shop.final(job_id))
    error = shop.report(job_id)['error']
    assert error['code'] == 'delivery.printer_unreachable_at_start'
    assert error['message'] == ('The computer next to the printer could not reach the '
                                'printer for 10 minutes.')


def test_a_start_the_printer_ignores_has_its_seconds_in_the_sentence(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    shop.printer.start = lambda name: True              # accepted; nothing happens
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    error = shop.report(job_id)['error']
    assert error['code'] == 'delivery.start_timeout'
    assert error['message'] == ('The printer did not show the print as started within 300 '
                                'seconds.')


def test_a_link_that_flaps_every_few_seconds_still_delivers(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    shop.link.flap_period = 3
    job_id = shop.send()
    assert shop.drive(1800, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1


def test_a_very_slow_but_alive_link_delivers(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    for exchange in EXCHANGES:
        shop.link.inject(exchange, *['slow'] * 5)
    job_id = shop.send()
    assert shop.drive(1800, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'


def test_a_lost_acknowledgement_is_repeated_and_counted_once(tmp_path):
    shop = Shop(tmp_path)
    job_id, finished = deliver_with(shop, 'ack', ['late', 'late'])
    assert shop.report(job_id)['state'] == 'done'
    acks = [path for _m, path in shop.link.delivered if path.endswith('/ack')]
    assert len(acks) >= 2                          # the relay saw it more than once ...
    assert len(shop.printer.started) == 1          # ... and nothing happened twice


def test_two_daemons_claiming_the_same_pairing_start_the_file_once(tmp_path):
    """The second daemon runs the whole job while the first is at the start gate: both
    have the file uploaded, both ask the gate, and only one may start it."""
    shop = Shop(tmp_path)
    shop.online()
    second = shop.new_daemon(instance='second-daemon')
    shop.loops.append(second)
    def the_other_runs_the_job():
        shop.advance(rl.SYNC_INTERVAL + 1)         # its next sync is due
        for loop in shop.loops:
            if loop.running_job_id is None:        # not the one at the gate now
                loop.tick()

    shop.link.before['start'] = the_other_runs_the_job
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    assert len(shop.printer.started) == 1
    assert shop.report(job_id)['state'] == 'done'
    gates = [path for _m, path in shop.link.delivered if path.endswith('/start')]
    assert len(gates) == 2, ' | '.join(shop.logged)   # both asked; one was refused


def test_a_clean_delivery_leaves_nothing_in_the_daemons_log_that_looks_like_an_error(
        tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    alarming = [line for line in shop.logged
                if any(word in line.lower() for word in ('error', 'fail', 'traceback',
                                                         'unexpected', 'could not'))]
    assert alarming == []
    # It says plainly what it is doing, stage by stage.
    for words in ('paired with the relay', 'downloading the sliced file',
                  'uploading to the printer', 'starting the print', 'acknowledged: ok'):
        assert any(words in line for line in shop.logged), words


def test_a_relay_that_restarts_reads_in_the_daemons_log_as_routine(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    shop.link.inject('sync', 'reset_after')
    shop.drive(30)
    lines = [line for line in shop.logged if 'network:' in line]
    assert lines and 'it may be restarting' in lines[0]
    assert any('the relay is answering again' in line for line in shop.logged)


def test_a_daemon_clock_wrong_by_hours_changes_nothing(tmp_path):
    shop = Shop(tmp_path, daemon_clock_offset=-9 * 3600)
    shop.online()
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'


@pytest.mark.parametrize('point', ['after_send', 'before_download', 'before_start_gate',
                                   'before_ack', 'after_start'])
def test_the_relay_restarting_mid_job_ends_in_a_defined_state_with_an_error_report(
        tmp_path, point):
    shop = Shop(tmp_path)
    shop.online()
    job_id = shop.send()
    hooks = {'before_download': 'download', 'before_start_gate': 'start',
             'before_ack': 'ack'}
    if point == 'after_send':
        shop.restart_relay()
    elif point in hooks:
        shop.link.before[hooks[point]] = shop.restart_relay
    else:
        shop.printer.after_start = shop.restart_relay
    shop.drive(900)
    shop.status()                                   # the caller presents the code again
    shop.drive(300)
    resp = shop.pages.get(f'/printer/jobs/{job_id}', base_url='https://relay.test')
    assert resp.status_code == 404
    assert resp.get_json()['error_report']['code'] == 'delivery.job_unknown'
    if point in ('before_ack', 'after_start'):
        assert len(shop.printer.started) == 1      # it was printing already: once
    else:
        assert shop.printer.started == []          # unknown at the gate: never started
    assert not shop.errors
    assert shop.status()['online'] is True           # the daemon carries on
    assert shop.loops[0].running_job_id is None


@pytest.mark.parametrize('point', ['before_pick_up', 'at_download', 'mid_upload',
                                   'at_start_gate', 'after_start', 'at_ack'])
def test_the_daemon_restarting_mid_job_never_starts_twice_and_loses_nothing(tmp_path, point):
    from link_faults import die
    shop = Shop(tmp_path)
    shop.online()
    job_id = shop.send()
    if point == 'before_pick_up':
        shop.restart_daemon()
    elif point == 'mid_upload':
        shop.printer.before_upload = die
    elif point == 'after_start':
        shop.printer.after_start = die
    else:
        shop.link.before[{'at_download': 'download', 'at_start_gate': 'start',
                          'at_ack': 'ack'}[point]] = die
    assert shop.drive(1200, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1
    assert_truthful(shop, job_id)


@pytest.mark.parametrize('waiting_in', ['waiting_for_printer', 'downloading', 'starting'])
def test_cancel_while_the_daemon_is_unreachable_takes_effect_when_it_returns(tmp_path,
                                                                             waiting_in):
    """The daemon holds the job and is cut off; the caller cancels; when the link returns
    the cancel reaches it, the file is never started, and the job ends cancelled."""
    shop = Shop(tmp_path)
    shop.online()
    if waiting_in == 'waiting_for_printer':
        shop.printer.off = True
    elif waiting_in == 'downloading':
        shop.link.inject('download', 'timeout', 'timeout')
    else:
        shop.link.inject('start', 'timeout', 'timeout', 'timeout')
    job_id = shop.send()
    answers = []

    def cut_off_and_cancel():
        shop.link.down_until = shop() + 120
        answers.append(shop.pages.post(f'/printer/jobs/{job_id}/cancel',
                                       base_url='https://relay.test'))

    shop.at(8, cut_off_and_cancel)
    assert shop.drive(900, lambda: shop.final(job_id))
    assert answers[0].status_code == 202, answers[0].get_json()
    assert answers[0].get_json()['outcome'] == 'cancelling'
    assert shop.report(job_id)['state'] == 'cancelled'
    assert shop.printer.started == []
    assert shop.printer.received == {}             # nothing left on the printer
    assert_truthful(shop, job_id)


def test_the_printer_off_when_the_job_arrives_and_on_later(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    shop.printer.off = True
    job_id = shop.send()
    seen = []
    shop.at(120, lambda: seen.append(shop.report(job_id)))
    shop.at(130, lambda: setattr(shop.printer, 'off', False))
    assert shop.drive(900, lambda: shop.final(job_id))
    assert (seen[0]['state'], seen[0]['stage']) == ('running', 'waiting_for_printer')
    assert shop.report(job_id)['state'] == 'done'


def test_cancel_after_the_start_is_refused_and_the_print_goes_on(tmp_path):
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 600
    shop.online()
    job_id = shop.send()
    shop.drive(300, lambda: shop.printer.started)
    resp = shop.pages.post(f'/printer/jobs/{job_id}/cancel', base_url='https://relay.test')
    assert resp.status_code == 409
    assert resp.get_json()['error_report']['code'] == 'delivery.cancel_too_late'
    assert shop.drive(900, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'


def test_the_printer_dropping_off_mid_print_marks_it_stale_and_it_recovers(tmp_path):
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 900
    shop.online()
    job_id = shop.send()
    shop.drive(300, lambda: shop.printer.started)
    shop.drive(10)
    fresh = shop.report(job_id)
    assert 'stale' not in fresh and fresh['stage'] == 'printing'
    shop.printer.off = True
    shop.drive(rl.SYNC_INTERVAL + 1)                   # the next sync carries the news
    dropped = shop.report(job_id)
    assert (dropped['state'], dropped['stale']) == ('running', True)
    shop.drive(60)
    assert shop.report(job_id)['stale'] is True
    shop.printer.off = False
    shop.drive(rl.SYNC_INTERVAL + 1)
    assert 'stale' not in shop.report(job_id)
    assert shop.drive(1200, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert_truthful(shop, job_id)


# --- property-based: random faults on both links ------------------------------------------

fault_lists = st.dictionaries(st.sampled_from(EXCHANGES),
                              st.lists(st.sampled_from(FAULTS + DOWNLOAD_FAULTS), max_size=4),
                              max_size=5)
printer_off = st.lists(st.tuples(st.integers(0, 600), st.integers(1, 200)), max_size=3)
printer_quiet = st.lists(st.tuples(st.integers(0, 600), st.integers(1, 900)), max_size=2)


def assert_started_only_on_fresh_word_of_a_free_printer(shop):
    """Round 3, defect 3: no start command while the printer's last report shows a print
    going on, or is older than the daemon's limit for fresh word."""
    for evidence in shop.printer.start_evidence:
        assert evidence is not None
        assert evidence['state'] in ('idle', 'finished', 'error'), evidence
        assert evidence['report_age_s'] <= rl.FRESH_REPORT_SECONDS, evidence


@settings(max_examples=40, deadline=None, derandomize=True, database=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture,
                                 HealthCheck.too_slow])
@given(faults=fault_lists, outages=printer_off, down=st.integers(0, 400),
       restart_daemon_at=st.one_of(st.none(), st.integers(1, 600)),
       jitter=st.floats(0, 1),
       after_start=st.one_of(st.none(), st.tuples(st.sampled_from(['link', 'printer']),
                                                  st.integers(1, 1500))),
       quiet=printer_quiet)
def test_random_faults_never_print_twice_and_always_tell_the_truth(
        tmp_path_factory, faults, outages, down, restart_daemon_at, jitter, after_start,
        quiet):
    """`after_start` cuts the link or the printer for up to 25 minutes from just after the
    start command: past the daemon's start wait and the relay's 15-minute deadline. A print
    that ran must then end done, never failed (defect 1).

    Every outage and the daemon's death are placed on the shop's timers (round 2, defect
    6), so they happen wherever the daemon is at that moment: inside its job's waits as
    well as between syncs. The printer cut after the start begins in the start command
    itself, before the daemon has seen the print."""
    from link_faults import die
    shop = Shop(tmp_path_factory.mktemp('shop'), rand=lambda: jitter)
    shop.online(seconds=600)
    for exchange, kinds in faults.items():
        shop.link.inject(exchange, *kinds)
    if after_start is not None:
        side, seconds = after_start

        def cut():
            if side == 'link':
                shop.link.down_until = shop() + seconds
            else:
                shop.printer.outage(shop, 0, seconds)

        shop.printer.after_start = cut
    job_id = shop.send()
    shop.link.down_until = shop() + down if down else None
    for at, length in outages:
        shop.printer.outage(shop, at, length)
    for at, length in quiet:
        shop.printer.quiet(shop, at, length)
    if restart_daemon_at is not None:
        shop.at(restart_daemon_at, die)
    for _second in range(3600):
        try:
            shop.advance(1)
            shop.tick()
        except DaemonDied:
            shop.restart_daemon()       # killed by a timer between two ticks
        if shop.final(job_id):
            break
    report = shop.report(job_id)
    assert report is not None
    assert len(shop.printer.started) <= 1
    assert_started_only_on_fresh_word_of_a_free_printer(shop)
    if shop.printer.started and shop.printer.finished_ours:
        # The printer ran our file to its end: the job never says it failed.
        assert report['state'] in ('done', 'running'), report
    if report['state'] == 'running':
        # Still in progress after an hour: only honest if it says what it waits for.
        assert report['stage'] in ('printing', 'waiting_for_person', 'waiting_for_printer',
                                   'starting')
    assert_truthful(shop, job_id)
    assert_no_tight_loop(shop, 4200)


def test_an_outage_on_the_timers_reaches_the_job_inside_its_wait(tmp_path):
    """Round 2, defect 6: the printer cut in the start command itself is seen by the
    daemon's start wait (it waits, not counting), not only by a later sync."""
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 600
    shop.printer.after_start = lambda: shop.printer.outage(shop, 0, 90)
    shop.online()
    job_id = shop.send()
    assert shop.drive(1800, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert any('so the wait is not counted' in line for line in shop.logged)
    assert len(shop.printer.started) == 1


# --- round 2: the printer waiting for a person, on the whole path (defect 1) -------------

H2S_RUNNING = {'gcode_state': 'RUNNING', 'stg_cur': 0, 'mc_percent': 30,
               'mc_remaining_time': 20, 'layer_num': 5, 'total_layer_num': 50,
               'print_error': 0, 'hms': []}


def to_printing(shop):
    shop.printer.print_seconds = 100 * 3600
    shop.online()
    job_id = shop.send()
    assert shop.drive(300, lambda: (shop.report(job_id) or {}).get('stage') == 'printing')
    return job_id


def printer_says(shop, **fields):
    """The stand-in printer reports this H2S document (mapped as the daemon maps it)."""
    document = dict(H2S_RUNNING, subtask_name=shop.printer._snapshot['job_name'], **fields)
    shop.printer._snapshot = pr.map_status(document, printer=shop.printer._snapshot['printer'])


@pytest.mark.parametrize('fault', [
    {'gcode_state': 'PAUSE', 'stg_cur': 6, 'print_error': 0x07008011},     # filament out
    {'gcode_state': 'PAUSE', 'stg_cur': 17, 'print_error': 0x0500400E},    # door open
    {'gcode_state': 'PAUSE', 'stg_cur': 16},                               # paused by hand
    {'print_error': 0x07008011},                                           # code while running
    {'hms': [{'attr': 0x07008000, 'code': 0x00020001}]},                   # serious, clears
], ids=['filament_out', 'door_open', 'paused_by_hand', 'code_while_running', 'serious_hms'])
def test_a_fault_someone_clears_at_the_printer_ends_done_not_failed(tmp_path, fault):
    """The reviewer's probe H on the whole path: the printer waits for a person, the job
    says so with what to do there, the print resumes and finishes, and the job is done."""
    shop = Shop(tmp_path)
    job_id = to_printing(shop)
    printer_says(shop, **fault)
    shop.drive(30)
    during = shop.report(job_id)
    assert (during['state'], during['stage']) == ('running', 'waiting_for_person'), during
    assert during['at_the_printer'] and during['waiting_label']
    printer_says(shop, mc_percent=31)
    shop.drive(30)
    assert shop.report(job_id)['stage'] == 'printing'
    printer_says(shop, gcode_state='FINISH', stg_cur=255, mc_percent=100)
    assert shop.drive(60, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert_truthful(shop, job_id)


def test_the_filament_wait_names_the_code_and_its_meaning(tmp_path):
    shop = Shop(tmp_path)
    job_id = to_printing(shop)
    printer_says(shop, gcode_state='PAUSE', stg_cur=6, print_error=0x07008011)
    shop.drive(30)
    report = shop.report(job_id)
    assert (report['waiting_for'], report['printer_error'], report['printer_error_meaning']) \
        == ('paused_filament_runout', 'PRINT_ERROR_07008011', 'the filament ran out')
    assert report['at_the_printer'] == ("Load new filament, then resume the print on the "
                                        "printer's screen.")


def test_an_error_that_ends_the_print_fails_it_with_the_printers_code(tmp_path):
    shop = Shop(tmp_path)
    job_id = to_printing(shop)
    printer_says(shop, gcode_state='FAILED', stg_cur=255, print_error=0x07008011)
    assert shop.drive(60, lambda: shop.final(job_id))
    error = shop.report(job_id)['error']
    assert error['code'] == 'delivery.print_failed'
    assert error['message'] == 'The print failed partway through: the filament ran out.'


# --- round 2: a 404 that is not the relay's own answer (defect 2) -------------------------

def answer_once_with_a_404_page(shop, exchange):
    real_send = shop.link._send
    used = []

    def send(method, url, **kwargs):
        if url.endswith(f'/{exchange}') and not used:
            used.append(url)
            return Canned(404, '<html>Application not found</html>', 'text/html')
        return real_send(method, url, **kwargs)

    shop.link._send = send
    return used


def test_a_404_page_on_the_ok_acknowledgement_never_blocks_the_queue(tmp_path):
    """The reviewer's probe G: the job slot used to be held for ever. The daemon now
    retries the acknowledgement, the relay frees the slot when the print ends either way,
    and the next send is accepted."""
    shop = Shop(tmp_path)
    shop.online()
    used = answer_once_with_a_404_page(shop, 'ack')
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    assert used and shop.report(job_id)['state'] == 'done'
    assert any('could not acknowledge' in line for line in shop.logged)
    shop.drive(120)
    assert shop.status()['job'] is None
    assert shop.loops[0].pending_acks == {}
    shop.printer._snapshot = shop.printer._idle()
    shop.drive(10)
    second = shop.send()                            # accepted: the queue is free
    assert shop.drive(900, lambda: shop.final(second))
    assert shop.report(second)['state'] == 'done'


def test_a_404_page_at_the_start_gate_is_asked_again_and_starts_once(tmp_path):
    shop = Shop(tmp_path)
    shop.online()
    used = answer_once_with_a_404_page(shop, 'start')
    job_id = shop.send()
    assert shop.drive(900, lambda: shop.final(job_id))
    assert used and shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1
    assert shop.printer.deleted == []                # never removed as "unknown"


# --- round 2: a job past the gate that nobody can hear (defects 3 and 6) ------------------

def test_a_printer_off_for_a_day_shows_its_true_age_then_ends_with_the_outcome_unknown(
        tmp_path):
    """Switched off mid-print and never back. The whole-path stale age is the printer's
    true age (defect 6); after a day of it the relay stops following (defect 3), saying the
    outcome is unknown, and the queue is free for the printer's return."""
    shop = Shop(tmp_path)
    job_id = to_printing(shop)
    shop.printer.off = True
    shop.drive(23 * 3600, step=60)
    report = shop.report(job_id)
    assert (report['state'], report['stale']) == ('running', True)
    assert report['stale_age_s'] >= 23 * 3600 - 120
    shop.drive(3600 + 120, step=60)
    report = shop.report(job_id)
    assert (report['state'], report['error']['code']) == ('failed', 'delivery.outcome_unknown')
    assert shop.status()['job'] is None
    shop.printer._snapshot = shop.printer._idle()
    shop.printer.off = False
    shop.drive(10)
    assert shop.send()
    assert_truthful(shop, job_id)


def test_the_caller_stops_following_a_job_whose_daemon_is_gone(tmp_path):
    """The reviewer's case D: the start command went out and the shop computer was never
    heard from again. The caller stops following; the job slot is free."""
    shop = Shop(tmp_path)
    shop.online()
    # The shop computer's link is gone for good the moment the start command went out.
    shop.printer.after_start = lambda: setattr(shop.link, 'down_until', shop() + 10 ** 9)
    job_id = shop.send()
    shop.drive(300, lambda: shop.printer.started)
    shop.drive(60)
    # The daemon's word that the command went never reached the relay: the refusal says
    # the start may have been sent, never that the print started (review 4, defect 3).
    refused_too_late = shop.pages.post(f'/printer/jobs/{job_id}/cancel', base_url=BASE)
    report = refused_too_late.get_json()['error_report']
    assert report['code'] == 'delivery.start_being_sent'
    assert 'started' not in report['message']
    resp = shop.pages.post(f'/printer/jobs/{job_id}/stop-following', base_url=BASE)
    assert resp.status_code == 200
    assert resp.get_json()['progress']['error']['code'] == 'delivery.outcome_unknown'
    assert shop.status()['job'] is None
    assert len(shop.printer.started) == 1


def test_stop_following_a_print_the_printer_still_reports_is_refused(tmp_path):
    shop = Shop(tmp_path)
    job_id = to_printing(shop)
    resp = shop.pages.post(f'/printer/jobs/{job_id}/stop-following', base_url=BASE)
    assert resp.status_code == 409
    assert resp.get_json()['error_report']['code'] == 'delivery.still_reporting'
    assert dl.FOLLOWING >= {shop.report(job_id)['stage']}


# --- round 3: a second file after stop-following, with the status stream quiet ------------

def quiet_after_the_first_upload(shop, quiet_seconds):
    """The reviewer's W1: the status stream goes silent (socket open, the idle document
    kept) and the first file prints for an hour. Two minutes after the send the caller
    stops following the first delivery job and sends a second.

    Since review 4 (defect 3) every wait comes before the start gate, so a stream silent
    from the first upload on would never let the first file start at all; the silence now
    begins the moment the first start command goes, before the printer has shown the print
    (its last document is the idle one), which is the case W1 is about."""
    shop.printer.print_seconds = 3600
    shop.online()
    first = shop.send()

    def go_quiet():
        shop.printer.quiet(shop, 0, quiet_seconds)
        shop.printer.frozen = dict(shop.printer._idle())

    shop.printer.after_start = go_quiet
    seen = {}

    def give_up_and_send_again():
        seen['stop'] = shop.pages.post(f'/printer/jobs/{first}/stop-following',
                                       base_url=BASE).status_code
        resp = shop.pages.post('/printer/jobs', json={'token': 'tok'}, base_url=BASE)
        seen['send'] = resp.status_code
        seen['second'] = resp.get_json().get('job_id')

    shop.at(120, give_up_and_send_again)
    return first, seen


def test_a_second_file_waits_for_fresh_word_and_is_refused_by_the_running_first(tmp_path):
    shop = Shop(tmp_path)
    first, seen = quiet_after_the_first_upload(shop, quiet_seconds=6 * 60)
    # The daemon left the first job's start wait and holds the second, waiting honestly.
    shop.at(240, lambda: seen.update(stage=shop.report(seen['second'])['stage']))
    assert shop.drive(20 * 60, lambda: 'second' in seen and shop.final(seen['second']))
    assert (seen['stop'], seen['send'], seen['stage']) == (200, 202, 'waiting_for_printer')
    assert any('no longer holds this job' in line for line in shop.logged)
    second = seen['second']
    report = shop.report(second)
    assert report['error']['code'] == 'delivery.printer_busy_at_start'
    assert report['error']['message'].startswith('The printer was busy with another print')
    assert len(shop.printer.started) == 1                     # the first file, only
    assert_started_only_on_fresh_word_of_a_free_printer(shop)
    assert_truthful(shop, second)


def test_a_second_file_waiting_for_fresh_word_can_be_cancelled(tmp_path):
    shop = Shop(tmp_path)
    first, seen = quiet_after_the_first_upload(shop, quiet_seconds=10 ** 6)

    def cancel_while_waiting():
        # The daemon's job runs inside a tick here, so the caller acts on the shop's timers.
        seen['stage'] = shop.report(seen['second'])['stage']
        seen['cancel'] = shop.pages.post(f"/printer/jobs/{seen['second']}/cancel",
                                         base_url=BASE).status_code

    shop.at(240, cancel_while_waiting)
    assert shop.drive(15 * 60, lambda: 'second' in seen and shop.final(seen['second']))
    assert (seen['stage'], seen['cancel']) == ('waiting_for_printer', 202)
    assert shop.report(seen['second'])['state'] == 'cancelled'
    assert len(shop.printer.started) == 1


def test_a_printer_that_stays_quiet_ends_the_second_file_unstarted(tmp_path):
    shop = Shop(tmp_path)
    first, seen = quiet_after_the_first_upload(shop, quiet_seconds=10 ** 6)
    assert shop.drive(20 * 60, lambda: 'second' in seen and shop.final(seen['second']))
    report = shop.report(seen['second'])
    assert report['error']['code'] == 'delivery.printer_unreachable_at_start'
    assert 'no whole, fresh report' in report['error']['detail']
    assert len(shop.printer.started) == 1
    assert_started_only_on_fresh_word_of_a_free_printer(shop)


def test_a_quiet_printer_at_the_start_command_is_asked_and_started_on_fresh_word(tmp_path):
    """The stream goes quiet after the upload and speaks again a minute later: the start
    command waits for that word."""
    shop = Shop(tmp_path)
    shop.printer.print_seconds = 300
    shop.online()
    job_id = shop.send()

    def quiet_now():
        shop.printer.quiet(shop, 0, 60)
        shop.printer.frozen = dict(shop.printer.frozen)
        shop.printer.quiet_since -= 30            # the last document is already 30 s old

    shop.printer.before_upload = quiet_now
    assert shop.drive(1200, lambda: shop.final(job_id))
    assert shop.report(job_id)['state'] == 'done'
    assert len(shop.printer.started) == 1
    assert_started_only_on_fresh_word_of_a_free_printer(shop)
    assert any('waiting for a fresh report from the printer' in line for line in shop.logged)
