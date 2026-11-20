"""The random sequences' known catches, written out by hand, for the fast suite.

The three property tests (marker `properties`, `make test-properties`) take seconds, so
they are not in the fast suite. In their place the fast suite runs one sequence for each
fault they are known to catch: each found by putting the fault back in a scratch copy and
running the property tests, or, for G4 and N2 (which they no longer reach), written to
reach it. Each runs through the same function and the same invariants as its property
test, so a sequence here fails the moment its fault comes back.

The faults, by the names review 6 gave them:

| Name | The fault |
|---|---|
| G2 | a picture without the main state counts as fresh |
| G4 | no wait for a free printer before the start gate is asked |
| G9 | a cancel past the gate always says the start command was sent |
| G12 | a start command that raises is taken as refused |
| G13 | a reconnect does not make the picture not whole |
| N1 | a damaged note does not hold the printer |
| N2 | the note is written only after the start command, not before it |
| N3 | a hold rebuilt from a `sending` note claims the command went |
| N7 | the relay takes `start_not_shown` as word that the command went |
"""

import pytest

from test_link_faults import faults_case
from test_start_decided import resend_case, starts_case

STARTS = [
    pytest.param(dict(show_after=None, previous_end='error', linger=True,
                      quiet=[(42, 35), (76, 57)], stop_at=39, whole_after=18,
                      someone=(0, 43), death='noted', relay_restart_at=70),
                 id='G2-a-partial-picture-is-not-fresh'),
    pytest.param(dict(show_after=40, previous_end='idle_error', linger=True,
                      whole_after=17, someone=(14, 23), cancel_at=27, death='noted',
                      start_fault='after', relay_restart_at=27),
                 id='G9-N3-N7-a-cancel-never-says-a-command-went-that-may-not-have'),
    pytest.param(dict(show_after=None, previous_end='error', linger=True,
                      partial=[(21, 2), (73, 21)], quiet=[(79, 30)],
                      outages=[(33, 34), (72, 23)], whole_after=17, start_fault='after'),
                 id='G12-a-start-command-that-raises-may-have-gone'),
    pytest.param(dict(show_after=None, previous_end='finished', partial=[(55, 26), (69, 27)],
                      quiet=[(50, 22)], outages=[(58, 38), (49, 31)], resend_at=15,
                      whole_after=2, someone=(0, 16), start_fault='after'),
                 id='G13-a-reconnect-makes-the-picture-not-whole'),
]

RESENDS = [
    pytest.param(dict(show_after=49, previous_end='error', quiet_at=2, quiet_for=18,
                      stop_after=12, resend_after=1, restart_at=38, whole_after=10,
                      relay_restart='relay', damage_note=True),
                 id='N1-a-damaged-note-holds-the-printer'),
    pytest.param(dict(show_after=50, death='sent', relay_restart='both'),
                 id='N2-the-note-is-written-before-the-command'),
]

FAULTS = [
    pytest.param(dict(faults={'sync': ['truncated'],
                              'ack': ['reset_after', '429_hint', '503', 'wrong_content']},
                      outages=[(78, 13), (54, 199)], down=50, jitter=0.5303905652539501,
                      after_start=('link', 1207), quiet=[(143, 58), (273, 379)],
                      whole_after=38, quiet_from_upload=(2, 1), death='gate',
                      start_fault='before'),
                 id='G2-the-gate-is-asked-only-on-a-whole-fresh-picture'),
    pytest.param(dict(quiet_from_upload=(60, 3)),
                 id='G4-the-wait-for-a-free-printer-comes-before-the-gate'),
]


@pytest.mark.parametrize('sequence', STARTS)
def test_a_start_sequence(tmp_path, sequence):
    starts_case(tmp_path, **sequence)


@pytest.mark.parametrize('sequence', RESENDS)
def test_a_resend_sequence(tmp_path, sequence):
    resend_case(tmp_path, **sequence)


@pytest.mark.parametrize('sequence', FAULTS)
def test_a_fault_sequence(tmp_path, sequence):
    faults_case(tmp_path, **sequence)
