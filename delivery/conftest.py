"""Every test's waits have a bound.

Each sleep a test injects into the daemon (the run loop's, the configuration wait's, each
command's) is wrapped in daemon_fakes.SleepBound: a wait in the code under test that never
ends -- a regression, a mutation -- fails the test in seconds with a message naming it,
instead of spinning for ever on a fake clock. Waits on real threads and events carry their
own timeouts in the tests that use them.

The run loop's `sleep` is a property here, not a plain attribute: whatever a test assigns to
`loop.sleep`, in `__init__` or afterwards, is wrapped as it is stored, so no test can put an
unbounded sleep in its place.

Two more layers sit outside every test: the fake clocks count their steps and fail past
daemon_fakes.CLOCK_STEP_LIMIT (so a spinning loop cannot grow without limit), and
pytest-timeout ends any test that runs past the limit set in pyproject.toml.
"""

import functools

import pytest

from daemon_fakes import SleepBound


def _bounded(function, what):
    @functools.wraps(function)
    def call(*args, **kwargs):
        if kwargs.get('sleep') is not None and not isinstance(kwargs['sleep'], SleepBound):
            kwargs['sleep'] = SleepBound(kwargs['sleep'], what)
        return function(*args, **kwargs)
    return call


def _get_sleep(loop):
    return loop.__dict__['_bounded_sleep']


def _set_sleep(loop, value):
    if not isinstance(value, SleepBound):
        value = SleepBound(value, 'the run loop')
    loop.__dict__['_bounded_sleep'] = value


@pytest.fixture(autouse=True)
def bounded_sleeps(monkeypatch):
    from penguin_delivery_daemon import __main__ as daemon_main
    from penguin_delivery_daemon import config, run_loop

    monkeypatch.setattr(run_loop.RunLoop, 'sleep', property(_get_sleep, _set_sleep),
                        raising=False)
    monkeypatch.setattr(config, 'wait_for_config',
                        _bounded(config.wait_for_config, 'wait_for_config'))
    for name in ('cmd_pair', 'cmd_run', 'cmd_status', 'cmd_record', 'wait_for_paired_config',
                 '_connect_and_identify'):
        monkeypatch.setattr(daemon_main, name, _bounded(getattr(daemon_main, name), name))
