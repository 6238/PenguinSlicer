"""Shared stand-ins for the relay's tests. Nothing here touches a socket, a file outside
pytest's tmp_path, or the real clock."""

from penguin_delivery_relay import SlicedFile, Team, create_app

CODE = '7K3MQ9XW'
SECRET = 'test-secret-key'

IDLE = {'state': 'idle', 'file': '', 'percent': None, 'remaining_min': None,
        'layer': 0, 'layers': 0, 'error': None,
        'printer': {'model': 'H2S', 'name': 'Shop H2S', 'serial': '01P00A'}}


def running(file_name, percent=42):
    return dict(IDLE, state='running', file=file_name, percent=percent,
                remaining_min=31, layer=87, layers=210)


class FakeClock:
    """An injectable wall clock. Every relay age, deadline and rate-limit window reads it."""

    #: The most advances one clock takes in a test: far above the busiest honest test (a
    #: day of syncs a second apart), far below a loop with no end, which then fails here.
    STEP_LIMIT = 1_000_000

    def __init__(self, now=1_789_300_000.0):
        self.now = now
        self.steps = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.steps += 1
        if self.steps > self.STEP_LIMIT:
            raise ClockRanAway(f'the relay\'s fake clock was advanced more than '
                               f'{self.STEP_LIMIT} times and the test had not ended; a loop '
                               'that moves simulated time has no end.')
        self.now += seconds


class ClockRanAway(BaseException):
    """A fake clock passed its step limit. A BaseException, so no `except Exception` in the
    code under test swallows it."""


class Caller:
    """The caller's side of the interface, as plain data the tests change.

    `team` is what identify() answers (None: no identity); `files` maps a posted token to
    the SlicedFile it names; `events` and `logged` collect what the relay reports."""

    def __init__(self, team=Team(pairing_code=CODE, team_number=6238,
                                 user='student@example.com')):
        self.team = team
        self.files = {}
        self.events = []
        self.logged = []
        self.identify_error = None
        self.identified = []
        self.find_error = None
        self.asked = []

    def identify(self, request):
        self.identified.append(request.path)
        if self.identify_error is not None:
            raise self.identify_error
        return self.team

    def find_sliced_file(self, token, team):
        """Records every (token, team) it is asked with, so a test can check the relay
        passes the team identify answered for -- the caller's duty to refuse another
        team's token depends on it."""
        self.asked.append((token, team))
        if self.find_error is not None:
            raise self.find_error
        return self.files.get(token)

    def on_event(self, kind, **fields):
        self.events.append((kind, fields))

    def log(self, *parts):
        self.logged.append(' '.join(str(p) for p in parts))

    def offer(self, tmp_path, token='tok', filename='sample_part.gcode.3mf',
              content=b'3mf-bytes', sliced_at=None):
        """Register a sliced file on disk under `token`."""
        path = tmp_path / f'{token}-{filename}'
        path.write_bytes(content)
        self.files[token] = SlicedFile(filename=filename, path=str(path),
                                       sliced_at=sliced_at)
        return str(path)


def make_app(caller, clock, **overrides):
    kwargs = dict(secret_key=SECRET, identify=caller.identify,
                  find_sliced_file=caller.find_sliced_file, clock=clock, log=caller.log,
                  on_event=caller.on_event)
    kwargs.update(overrides)
    return create_app(**kwargs)
