"""The relay's small parts on their own: the rate limiter, the sliced-file store, the
caller's data shapes and the app factory."""
import io

import pytest

from penguin_delivery_relay import SlicedFile, create_app, relay_of
from penguin_delivery_relay.limits import PRUNE_ABOVE, Limit, RateLimiter
from penguin_delivery_relay.sliced_files import SlicedFileStore

from relay_fakes import FakeClock


class TestRateLimiter:
    def test_a_window_allows_its_count_then_answers_the_wait(self):
        clock = FakeClock(100.0)
        limiter = RateLimiter(clock)
        limit = Limit(3, 60.0)
        assert [limiter.hit('r', 'k', limit) for _ in range(3)] == [None, None, None]
        clock.advance(15)
        assert limiter.hit('r', 'k', limit) == 45.0

    def test_the_window_opens_at_the_first_request_and_closes_after_its_period(self):
        clock = FakeClock(100.0)
        limiter = RateLimiter(clock)
        limit = Limit(1, 60.0)
        assert limiter.hit('r', 'k', limit) is None
        clock.advance(59.9)
        assert limiter.hit('r', 'k', limit) == pytest.approx(0.1)
        clock.advance(0.1)
        assert limiter.hit('r', 'k', limit) is None

    def test_routes_and_keys_count_separately(self):
        limiter = RateLimiter(FakeClock())
        limit = Limit(1, 60.0)
        assert limiter.hit('a', 'k', limit) is None
        assert limiter.hit('b', 'k', limit) is None
        assert limiter.hit('a', 'other', limit) is None
        assert limiter.hit('a', 'k', limit) is not None

    def test_expired_windows_are_pruned_once_the_table_is_large(self):
        clock = FakeClock()
        limiter = RateLimiter(clock)
        for n in range(PRUNE_ABOVE + 1):
            limiter.hit('r', n, Limit(1, 60.0))
        clock.advance(61)
        limiter.hit('r', 'fresh', Limit(1, 60.0))
        assert len(limiter) == 1

    def test_reset_forgets_every_count(self):
        limiter = RateLimiter(FakeClock())
        limiter.hit('r', 'k', Limit(1, 60.0))
        limiter.reset()
        assert len(limiter) == 0
        assert limiter.hit('r', 'k', Limit(1, 60.0)) is None

    def test_a_limit_names_itself_like_the_original_limiter(self):
        assert str(Limit(60, 60.0)) == '60 per 1 minute'
        assert str(Limit(5, 10.0)) == '5 per 10 seconds'


class TestSlicedFileStore:
    def test_a_path_is_held_as_it_is(self, tmp_path):
        path = tmp_path / 'part.gcode.3mf'
        path.write_bytes(b'x')
        store = SlicedFileStore(str(tmp_path / 'spool'))
        token = store.add('CODE', 'j1', SlicedFile(filename='part.gcode.3mf', path=str(path)))
        held = store.get(token)
        assert (held.path, held.owned, held.filename) == (str(path), False, 'part.gcode.3mf')

    def test_a_stream_is_copied_into_the_spool_and_deleted_on_discard(self, tmp_path):
        spool = tmp_path / 'spool'
        store = SlicedFileStore(str(spool))
        token = store.add('CODE', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'abc')))
        held = store.get(token)
        assert held.owned is True
        assert open(held.path, 'rb').read() == b'abc'
        store.discard(token)
        assert list(spool.iterdir()) == []
        assert store.get(token) is None
        store.discard(token)                        # twice is harmless

    def test_a_stream_that_fails_mid_copy_leaves_nothing(self, tmp_path):
        class Broken(io.RawIOBase):
            def readinto(self, buffer):
                raise OSError('the caller hung up')

        spool = tmp_path / 'spool'
        store = SlicedFileStore(str(spool))
        with pytest.raises(OSError):
            store.add('CODE', 'j1', SlicedFile(filename='p', stream=Broken()))
        assert list(spool.iterdir()) == []
        assert len(store) == 0

    def test_prune_keeps_held_jobs_and_drops_the_rest(self, tmp_path):
        store = SlicedFileStore(str(tmp_path / 'spool'))
        keep = store.add('A', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'1')))
        drop = store.add('B', 'j2', SlicedFile(filename='p', stream=io.BytesIO(b'2')))
        store.confirm(keep)
        store.confirm(drop)
        dropped_path = store.get(drop).path
        store.prune(lambda code, job_id: job_id == 'j1')
        assert store.get(keep) is not None
        assert store.get(drop) is None
        assert not (tmp_path / 'spool' / dropped_path).exists()

    def test_prune_leaves_an_entry_waiting_for_its_claim_alone(self, tmp_path):
        """A send holds the file before it claims the job; another request's housekeeping
        in between must not take it."""
        store = SlicedFileStore(str(tmp_path / 'spool'))
        token = store.add('A', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'1')))
        store.prune(lambda code, job_id: False)
        assert store.get(token) is not None
        store.confirm(token)
        store.prune(lambda code, job_id: False)
        assert store.get(token) is None
        assert list((tmp_path / 'spool').iterdir()) == []

    def test_a_discard_ends_the_wait_too(self, tmp_path):
        store = SlicedFileStore(str(tmp_path / 'spool'))
        token = store.add('A', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'1')))
        store.discard(token)
        assert store.get(token) is None
        assert store._awaiting_claim == set()

    def test_deleting_a_copy_that_is_already_gone_is_harmless(self, tmp_path):
        store = SlicedFileStore(str(tmp_path / 'spool'))
        token = store.add('A', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'1')))
        (tmp_path / 'spool' / store.get(token).path.rsplit('/', 1)[1]).unlink()
        store.discard(token)
        assert store.get(token) is None

    def test_without_a_spool_dir_a_private_temporary_one_is_made(self, tmp_path,
                                                                 monkeypatch):
        monkeypatch.setenv('TMPDIR', str(tmp_path))
        import tempfile
        monkeypatch.setattr(tempfile, 'tempdir', None)
        store = SlicedFileStore()
        token = store.add('A', 'j1', SlicedFile(filename='p', stream=io.BytesIO(b'1')))
        assert store.get(token).path.startswith(str(tmp_path))
        store.discard(token)


class TestSlicedFile:
    def test_exactly_one_source(self):
        with pytest.raises(ValueError):
            SlicedFile(filename='p')
        with pytest.raises(ValueError):
            SlicedFile(filename='p', path='/x', stream=io.BytesIO())


class TestCreateApp:
    def test_defaults_need_only_the_three_required_arguments(self):
        app = create_app(secret_key='k', identify=lambda request: None,
                         find_sliced_file=lambda token, team: None)
        ctx = relay_of(app)
        assert ctx.dev is False
        assert ctx.log is None and ctx.on_event is None
        client = app.test_client()
        assert client.get('/printer/status').status_code == 401   # nothing to log, no crash

    def test_two_apps_share_no_state(self):
        def make():
            return create_app(secret_key='k', identify=lambda request: None,
                              find_sliced_file=lambda token, team: None, clock=FakeClock())
        first, second = make(), make()
        relay_of(first).relay.note_code('7K3MQ9XW')
        assert relay_of(second).relay.status_for('7K3MQ9XW')['paired'] is False

    def test_the_caller_can_present_a_code_before_any_poll(self):
        app = create_app(secret_key='k', identify=lambda request: None,
                         find_sliced_file=lambda token, team: None, clock=FakeClock())
        relay_of(app).relay.note_code('7k3m-q9xw')
        client = app.test_client()
        resp = client.post('/printer/daemon/pair', json={'code': '7K3MQ9XW'},
                           base_url='https://relay.test')
        assert resp.status_code == 200
