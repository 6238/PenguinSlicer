"""The note of a start command in the daemon's home (start_record.py), and the hold it
gives a restarted daemon without help from the relay (review 5, defects 3 and 4)."""
import json
import os

import pytest

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_daemon import start_record as sr

from daemon_fakes import IDLE, JOB, SUFFIXED, running
from test_daemon_run_loop import RunLoopTestCase


class _Killed(BaseException):
    """Stands in for the process dying in the middle of a call."""


# -- the note itself ------------------------------------------------------------------

def test_a_note_written_is_read_back_whole(tmp_path):
    path = str(tmp_path / 'home' / 'start.json')
    sr.save(path, job_id='j8f3a2c1', remote_name=SUFFIXED, printer='01P00A',
            phase=sr.SENDING, wall=lambda: 0)
    note = sr.load(path)
    assert note == {'job_id': 'j8f3a2c1', 'remote_name': SUFFIXED, 'printer': '01P00A',
                    'phase': sr.SENDING, 'written_at': '1970-01-01T00:00:00Z'}
    sr.save(path, job_id='j8f3a2c1', remote_name=SUFFIXED, printer='01P00A',
            phase=sr.SENT)
    assert sr.load(path)['phase'] == sr.SENT
    assert os.listdir(tmp_path / 'home') == ['start.json']


def test_no_note_is_none(tmp_path):
    assert sr.load(str(tmp_path / 'start.json')) is None


@pytest.mark.parametrize('content', [
    b'', b'{"version": 1, "job_id": "j1"', b'[1, 2]', b'\xff\xfe',
    json.dumps({'version': 2, 'job_id': 'j1', 'remote_name': 'a', 'printer': '',
                'phase': 'sent'}).encode(),
    json.dumps({'version': 1, 'remote_name': 'a', 'printer': '', 'phase': 'sent'}).encode(),
    json.dumps({'version': 1, 'job_id': 'j1', 'remote_name': '', 'printer': '',
                'phase': 'sent'}).encode(),
    json.dumps({'version': 1, 'job_id': 'j1', 'remote_name': 'a', 'printer': 5,
                'phase': 'sent'}).encode(),
    json.dumps({'version': 1, 'job_id': 'j1', 'remote_name': 'a', 'printer': '',
                'phase': 'maybe'}).encode(),
    b' ' * (sr.MAX_BYTES + 1),
])
def test_a_note_that_cannot_be_understood_is_damaged(tmp_path, content):
    path = tmp_path / 'start.json'
    path.write_bytes(content)
    note = sr.load(str(path))
    assert isinstance(note, sr.Damaged), note
    assert note.reason and 'Damaged' in repr(note)


def test_a_note_that_cannot_be_read_is_damaged(tmp_path):
    (tmp_path / 'start.json').mkdir()                     # a directory where the note is
    note = sr.load(str(tmp_path / 'start.json'))
    assert isinstance(note, sr.Damaged) and 'could not be read' in note.reason


@pytest.mark.parametrize('where', ['write', 'fsync', 'replace'])
def test_a_crash_mid_write_leaves_the_old_note_whole_and_no_temporary_file(
        tmp_path, monkeypatch, where):
    path = str(tmp_path / 'start.json')
    sr.save(path, job_id='j00000001', remote_name='old-j00000001.gcode.3mf', printer='P',
            phase=sr.SENT)

    def killed(*args, **kwargs):
        raise _Killed()

    if where == 'write':
        monkeypatch.setattr(sr.json, 'dumps', killed)
    else:
        monkeypatch.setattr(sr.os, where, killed)
    with pytest.raises(_Killed):
        sr.save(path, job_id='j8f3a2c1', remote_name=SUFFIXED, printer='P',
                phase=sr.SENDING)
    assert sr.load(path)['job_id'] == 'j00000001'
    assert os.listdir(tmp_path) == ['start.json']


def test_a_write_that_fails_raises_and_leaves_no_note(tmp_path):
    blocker = tmp_path / 'not-a-folder'
    blocker.write_text('x')
    with pytest.raises(OSError):
        sr.save(str(blocker / 'start.json'), job_id='j1', remote_name='a', printer='',
                phase=sr.SENDING)


def test_clear_says_whether_the_note_is_gone(tmp_path):
    path = tmp_path / 'start.json'
    assert sr.clear(str(path)) is True                    # never there
    path.write_text('{}')
    assert sr.clear(str(path)) is True and not path.exists()
    path.mkdir()
    (path / 'x').write_text('x')
    assert sr.clear(str(path)) is False


# -- the note and the run loop --------------------------------------------------------

class NoteTestCase(RunLoopTestCase):
    def setUp(self):
        super().setUp()
        self.note = os.path.join(self.tmp, 'home', 'start.json')

    def make_noted(self, **overrides):
        return self.make_paired(start_record_path=self.note, **overrides)

    def restart(self, **overrides):
        """A new process with the same home: nothing in memory, the note on the disk."""
        return self.make_noted(instance='daemon-test-2', **overrides)

    def leave_unsettled(self):
        """The first job sends its command and leaves the wait (the relay no longer holds
        it) with the printer idle: the start is unsettled and the note stays."""
        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_noted()
        self.deliver(loop)
        self.relay.gate_outcomes = []
        assert self.printer.starts == [SUFFIXED]
        return loop


class TestTheNoteOfAStart(NoteTestCase):
    def test_the_note_is_written_before_the_command_marked_after_and_gone_when_settled(self):
        loop = self.make_noted()
        at_command = []
        original = self.printer.start

        def start(name):
            at_command.append(sr.load(self.note))
            return original(name)

        self.printer.start = start
        seen = []
        self.printer.starts_running = False

        def sleep(seconds):
            self.clock.sleep(seconds)
            seen.append(sr.load(self.note))
            self.printer.set(running(SUFFIXED))

        loop.sleep = sleep
        self.deliver(loop)
        assert at_command[0]['phase'] == sr.SENDING
        assert at_command[0]['job_id'] == 'j8f3a2c1'
        assert at_command[0]['remote_name'] == SUFFIXED
        assert at_command[0]['printer'] == '01P00A'
        assert seen[0]['phase'] == sr.SENT
        assert sr.load(self.note) is None
        assert self.relay.acks == [('j8f3a2c1', True, None)]

    def test_a_restarted_daemon_holds_the_printer_from_the_note_alone(self):
        """The relay restarted too, so it names no earlier start: the note holds the
        printer, and the next job waits START_SETTLE_SECONDS of fresh pictures."""
        self.leave_unsettled()
        loop = self.restart()
        assert (loop.hold.job_id, loop.hold.remote_name) == ('j8f3a2c1', SUFFIXED)
        assert loop.hold.start_known and not loop.hold.sent_here
        assert self.lines('an earlier run of this daemon sent the printer a start command')
        self.printer.starts_running = True
        before = self.clock.now
        stages = []
        loop.sleep = lambda s: (self.clock.sleep(s), stages.append(loop.job_progress['stage']))
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        assert self.relay.acks[-1] == ('j0000abcd', True, None)
        assert self.clock.now - before >= rl.START_SETTLE_SECONDS
        assert stages[0] == 'waiting_for_earlier_print'
        assert sr.load(self.note) is None
        assert self.printer.starts == [SUFFIXED, 'sample_part-j0000abcd.gcode.3mf']

    def test_a_restarted_daemon_refuses_the_next_job_when_the_noted_print_shows(self):
        self.leave_unsettled()
        loop = self.restart()
        loop.sleep = lambda s: (self.clock.sleep(s), self.printer.set(running(SUFFIXED)))
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        assert self.relay.ack_codes[-1] == 'delivery.printer_busy_at_start'
        assert self.printer.starts == [SUFFIXED]
        assert loop.hold is None and sr.load(self.note) is None

    def test_the_relays_gate_age_shortens_a_hold_from_the_note(self):
        self.leave_unsettled()
        loop = self.restart()
        self.printer.starts_running = True
        previous = {'id': 'j8f3a2c1', 'filename': 'sample_part.gcode.3mf',
                    'age_s': int(rl.START_SETTLE_SECONDS) + 1}
        before = self.clock.now
        self.deliver(loop, dict(JOB, id='j0000abcd', previous_start=previous))
        assert self.relay.acks[-1] == ('j0000abcd', True, None)
        assert self.clock.now == before                     # no wait for the hold
        assert sr.load(self.note) is None

    def test_a_young_gate_age_leaves_the_rest_of_the_hold(self):
        """The relay says the gate was 100 s ago: the hold from the note needs the other
        START_SETTLE_SECONDS - 100 s, not the whole time again, and not none."""
        self.leave_unsettled()
        loop = self.restart()
        self.printer.starts_running = True
        previous = {'id': 'j8f3a2c1', 'filename': 'sample_part.gcode.3mf', 'age_s': 100}
        before = self.clock.now
        self.deliver(loop, dict(JOB, id='j0000abcd', previous_start=previous))
        assert self.relay.acks[-1] == ('j0000abcd', True, None)
        waited = self.clock.now - before
        assert rl.START_SETTLE_SECONDS - 100 <= waited < rl.START_SETTLE_SECONDS - 90

    def test_the_job_of_the_note_offered_again_is_never_started_again(self):
        """Whatever the relay says (here: nothing of a start granted), the job the note
        names is only waited for."""
        self.leave_unsettled()
        loop = self.restart()
        loop.sleep = lambda s: (self.clock.sleep(s), self.printer.set(running(SUFFIXED)))
        self.deliver(loop, dict(JOB))
        assert self.printer.starts == [SUFFIXED]
        assert self.relay.acks[-1] == ('j8f3a2c1', True, None)

    def test_a_note_of_a_command_that_may_not_have_gone_never_says_it_went(self):
        """Died after the note and before the command: a restarted daemon holds the
        printer but its stage never says `start_sent`, so the relay never tells a caller
        the command went (defect 4)."""
        original = self.printer.start

        def die(name):
            raise _Killed()

        self.printer.start = die
        loop = self.make_noted()
        with pytest.raises(_Killed):
            self.deliver(loop)
        assert sr.load(self.note)['phase'] == sr.SENDING
        self.printer.start = original
        loop = self.restart()
        assert not loop.hold.start_known
        stages = []
        loop.sleep = lambda s: (self.clock.sleep(s), stages.append(dict(loop.job_progress)))
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=3))
        late = [s for s in stages if s['stage'] == 'start_not_shown']
        assert late and all(s.get('start_sent') is False for s in late)
        assert all(s.get('start_sent') is not True for s in stages)
        assert self.relay.ack_codes == ['delivery.start_timeout']
        assert 'cannot know whether the start command was sent' in self.relay.ack_details[0]
        assert self.printer.starts == []

    def test_a_note_of_a_command_that_went_says_so_after_a_restart(self):
        self.leave_unsettled()
        loop = self.restart()
        stages = []
        loop.sleep = lambda s: (self.clock.sleep(s), stages.append(dict(loop.job_progress)))
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=3))
        late = [s for s in stages if s['stage'] == 'start_not_shown']
        assert late and all(s.get('start_sent') is True for s in late)

    def test_a_note_about_another_printer_is_set_aside(self):
        sr.save(self.note, job_id='j00000001', remote_name='a-j00000001.gcode.3mf',
                printer='OTHER', phase=sr.SENT)
        loop = self.make_noted()
        assert loop.hold is None and sr.load(self.note) is None
        assert self.lines('names another printer')

    def test_a_note_that_cannot_be_written_means_no_start_command(self):
        blocker = os.path.join(self.tmp, 'home')
        with open(blocker, 'w') as fh:
            fh.write('a file where the home folder should be')
        loop = self.make_noted()
        self.deliver(loop)
        assert self.relay.ack_codes == ['delivery.start_not_recorded']
        assert (self.printer.starts, self.printer.deleted) == ([], [SUFFIXED])
        assert 'not started' in self.relay.ack_details[0]

    def test_a_note_that_cannot_be_marked_sent_still_holds(self):
        real = sr.save

        def save(path, **fields):
            if fields['phase'] == sr.SENT:
                raise OSError('disk full')
            return real(path, **fields)

        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_noted()
        rl.start_record.save = save
        try:
            self.deliver(loop)
        finally:
            rl.start_record.save = real
        assert self.lines('could not mark the note of the start command as sent')
        assert sr.load(self.note)['phase'] == sr.SENDING
        assert loop.hold is not None and loop.hold.start_known

    def test_a_refused_start_leaves_no_note(self):
        self.printer.start_result = False
        loop = self.make_noted()
        self.deliver(loop)
        assert self.relay.ack_codes == ['delivery.start_refused']
        assert sr.load(self.note) is None

    def test_a_note_that_cannot_be_removed_is_said_in_the_log(self):
        loop = self.leave_unsettled()
        real = sr.clear
        rl.start_record.clear = lambda path: False
        try:
            loop.sleep = lambda s: (self.clock.sleep(s), self.printer.set(running(SUFFIXED)))
            self.deliver(loop, dict(JOB, id='j0000abcd'))
        finally:
            rl.start_record.clear = real
        assert self.lines('could not remove')
        assert loop.hold is None


class TestADamagedNote(NoteTestCase):
    def damage(self):
        os.makedirs(os.path.dirname(self.note), exist_ok=True)
        with open(self.note, 'wb') as fh:
            fh.write(b'{"version": 1, "job_id": "j8f3')      # cut off mid-write

    def test_a_damaged_note_holds_the_printer_until_the_settle_time_of_whole_reports(self):
        self.damage()
        loop = self.make_noted()
        assert loop.hold is not None and loop.hold.remote_name is None
        assert self.lines('is not readable JSON')
        self.printer.starts_running = True
        before = self.clock.now
        stages = []
        loop.sleep = lambda s: (self.clock.sleep(s), stages.append(loop.job_progress['stage']))
        self.deliver(loop)
        assert stages[0] == 'waiting_for_earlier_print'
        assert self.clock.now - before >= rl.START_SETTLE_SECONDS
        assert self.relay.acks == [('j8f3a2c1', True, None)]
        assert self.lines('the start command of the unreadable note is settled: the printer '
                          'showed no print going')

    def test_pictures_that_are_not_whole_and_fresh_never_free_a_damaged_note(self):
        self.damage()
        loop = self.make_noted()
        self.printer.set(dict(IDLE, report_age_s=int(rl.FRESH_REPORT_SECONDS) + 1))
        self.deliver(loop)
        assert self.relay.ack_codes == ['delivery.printer_unreachable_at_start']
        assert self.printer.starts == [] and loop.hold is not None
        assert os.path.exists(self.note)

    def test_a_damaged_note_is_settled_by_a_print_going(self):
        self.damage()
        loop = self.make_noted()
        self.printer.set(running('someone_elses-j00000009'))
        self.deliver(loop)
        assert self.relay.ack_codes == ['delivery.printer_busy_at_start']
        assert loop.hold is None and not os.path.exists(self.note)
        assert self.lines('the printer is printing a file')

    def test_an_unreadable_note_holds_too(self):
        os.makedirs(self.note)
        loop = self.make_noted()
        assert loop.hold is not None and not loop.hold.start_known


class TestTheReasonAfterTheWait(RunLoopTestCase):
    """Review 5, defect 5: a job that waited behind the hold on a printer that answers on
    and off ends with the reason that happened, and the detail's figures are true."""

    def setUp(self):
        super().setUp()
        self.printer.starts_running = False

    def held(self):
        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_paired()
        self.deliver(loop)
        self.relay.gate_outcomes = []
        return loop

    def flapping(self, loop, quiet_of_60):
        def sleep(seconds):
            self.clock.sleep(seconds)
            quiet = (self.clock.now % 60) < quiet_of_60
            self.printer.set(dict(IDLE, report_age_s=60 if quiet else 0))

        loop.sleep = sleep

    def test_a_printer_answering_on_and_off_ends_as_the_earlier_start_unsettled(self):
        loop = self.held()
        self.printer.set(dict(IDLE, report_age_s=60))
        self.flapping(loop, 50)
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        assert self.relay.ack_codes[-1] == 'delivery.earlier_start_unsettled'
        assert self.relay.ack_fields[-1] == {'minutes': 10}
        detail = self.relay.ack_details[-1]
        counted = int(loop.hold.counted)
        assert 0 < counted < rl.START_SETTLE_SECONDS
        assert f'{counted} s of the {int(rl.START_SETTLE_SECONDS)} s' in detail
        assert 'job j8f3a2c1 (sample_part-j8f3a2c1.gcode.3mf) was sent a start command' \
            in detail
        assert 'whole, fresh reports from the printer for ' in detail
        assert self.printer.starts == [SUFFIXED]

    def test_a_printer_quiet_for_the_whole_wait_is_unreachable_for_ten_minutes(self):
        loop = self.held()
        self.printer.set(dict(IDLE, report_age_s=60))
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        assert self.relay.ack_codes[-1] == 'delivery.printer_unreachable_at_start'
        assert self.relay.ack_fields[-1] == {'minutes': 10}
        assert self.relay.ack_details[-1].startswith(
            'no whole, fresh report from the printer in the 600 s waited')

    def test_a_printer_that_answered_once_and_then_not_is_still_the_hold(self):
        """Fresh for the first look only, then quiet for the rest of the ten minutes, and
        quiet at the last look: the hold was the reason the job could not go on, and the
        detail says how little the printer answered."""
        loop = self.held()
        self.printer.set(dict(IDLE))

        def sleep(seconds):
            self.clock.sleep(seconds)
            self.printer.set(dict(IDLE, report_age_s=60))

        loop.sleep = sleep
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        assert self.relay.ack_codes[-1] == 'delivery.earlier_start_unsettled'
        detail = self.relay.ack_details[-1]
        assert 'whole, fresh reports from the printer for 0 s of the 600 s waited' in detail
        assert '60 s old' in detail
