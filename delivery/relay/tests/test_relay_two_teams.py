"""Two teams on one relay, through the routes: nothing of one team's job, status, result,
download or sliced file reaches the other.

The relay keys everything on the pairing code, except one thing it cannot check itself:
who owns a send token. It hands `find_sliced_file` the team that `identify` answered for
the request and trusts the answer, so these tests pin exactly which team it hands over."""
import io

from penguin_delivery_relay import SlicedFile, Team, relay_of
from penguin_delivery_relay import relay as relay_module

from relay_fakes import IDLE, SECRET, FakeClock, make_app, running

A = '7K3MQ9XW'
B = 'B2B2B2B2'
HTTPS = {'base_url': 'https://relay.test'}


def bearer(code):
    return {'Authorization': f'Bearer {relay_module.issue_token(code, SECRET)}'}


class TwoTeams:
    """One relay, two teams. The `X-Who` header chooses which team identify() answers for.
    find_sliced_file does what README-details.md asks of a caller: it answers only for a token the
    asking team owns."""

    def __init__(self, tmp_path):
        self.clock = FakeClock()
        self.teams = {'a': Team(pairing_code=A, team_number=1111, user='a@example.com'),
                      'b': Team(pairing_code=B, team_number=2222, user='b@example.com')}
        self.files = {}                 # token -> (owning team key, SlicedFile)
        self.asked = []
        self.logged = []
        self.events = []

        def identify(request):
            return self.teams[request.headers['X-Who']]

        def find(token, team):
            self.asked.append((token, team))
            owner, sliced = self.files.get(token, (None, None))
            return sliced if owner is not None and self.teams[owner] == team else None

        self.app = make_app(_NoCaller(), self.clock, identify=identify,
                            find_sliced_file=find, log=self.log, on_event=self.on_event,
                            spool_dir=str(tmp_path / 'spool'))
        self.relay = relay_of(self.app).relay
        self.client = self.app.test_client()
        for code in (A, B):
            self.relay.note_code(code)
            self.relay.note_daemon(code)
            self.relay.store_status(code, IDLE)

    def log(self, *parts):
        self.logged.append(' '.join(str(p) for p in parts))

    def on_event(self, kind, **fields):
        self.events.append((kind, fields))

    def offer(self, who, token, content):
        self.files[token] = (who, SlicedFile(filename=f'{who}.gcode.3mf',
                                             stream=io.BytesIO(content)))

    def get(self, who, path):
        return self.client.get(path, headers={'X-Who': who})

    def send(self, who, token):
        return self.client.post('/printer/jobs', json={'token': token},
                                headers={'X-Who': who})

    def sync(self, code, snapshot=IDLE):
        return self.client.post('/printer/daemon/sync', json=snapshot,
                                headers=bearer(code), **HTTPS).get_json()['job']

    def ack(self, code, job_id, **body):
        return self.client.post(f'/printer/daemon/jobs/{job_id}/ack', json=body,
                                headers=bearer(code), **HTTPS)


class _NoCaller:
    """make_app's defaults are all overridden here; this only satisfies its signature."""
    identify = find_sliced_file = log = on_event = None


def test_find_sliced_file_is_handed_exactly_the_team_identify_answered(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('b', 'tok-b', b'B')
    assert t.send('b', 'tok-b').status_code == 202
    t.send('a', 'tok-b')
    assert t.asked == [('tok-b', t.teams['b']), ('tok-b', t.teams['a'])]


def test_a_send_of_another_teams_token_is_refused_and_holds_nothing(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('b', 'tok-b', b'B')
    resp = t.send('a', 'tok-b')
    assert resp.status_code == 404
    assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_missing'
    assert len(relay_of(t.app).files) == 0
    assert t.sync(A) is None


def test_team_b_never_sees_team_a_job_status_or_result(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('a', 'tok-a', b'A')
    job_id = t.send('a', 'tok-a').get_json()['job_id']
    assert t.get('a', '/printer/status').get_json()['job']['id'] == job_id
    b = t.get('b', '/printer/status').get_json()
    assert b['job'] is None and b['last_result'] is None and b['code'] == 'B2B2-B2B2'
    assert job_id not in str(b)
    t.sync(A)
    t.ack(A, job_id, ok=False, error='download answered 404')
    assert t.get('a', '/printer/status').get_json()['last_result']['ok'] is False
    assert t.get('b', '/printer/status').get_json()['last_result'] is None


def test_team_b_daemon_is_never_offered_and_cannot_ack_team_a_job(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('a', 'tok-a', b'A')
    job_id = t.send('a', 'tok-a').get_json()['job_id']
    assert t.sync(B) is None
    resp = t.ack(B, job_id, ok=True)
    assert resp.status_code == 404
    assert t.get('a', '/printer/status').get_json()['job']['id'] == job_id
    assert t.sync(A)['id'] == job_id


def test_the_download_token_is_shown_to_no_caller_route_log_or_event(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('a', 'tok-a', b'A')
    sent = t.send('a', 'tok-a')
    token = t.sync(A)['download_path'].rsplit('/', 1)[1]
    for body in (sent.get_data(as_text=True),
                 t.get('a', '/printer/status').get_data(as_text=True),
                 t.get('b', '/printer/status').get_data(as_text=True)):
        assert token not in body
    assert not any(token in line for line in t.logged)
    assert not any(token in str(event) for event in t.events)


def test_both_teams_hold_a_job_at_once_and_each_download_serves_its_own_bytes(tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('a', 'tok-a', b'AAAA')
    t.offer('b', 'tok-b', b'BBBB')
    assert t.send('a', 'tok-a').status_code == 202
    assert t.send('b', 'tok-b').status_code == 202
    ja, jb = t.sync(A), t.sync(B)
    assert t.client.get(ja['download_path']).data == b'AAAA'
    assert t.client.get(jb['download_path']).data == b'BBBB'
    # A finishing must not take B's file with it.
    assert t.ack(A, ja['id'], ok=True).status_code == 200
    assert t.client.get(ja['download_path']).status_code == 404
    assert t.client.get(jb['download_path']).data == b'BBBB'


def test_a_printer_reporting_another_teams_job_id_does_not_clear_this_teams_result(
        tmp_path):
    t = TwoTeams(tmp_path)
    t.offer('a', 'tok-a', b'A')
    job_id = t.send('a', 'tok-a').get_json()['job_id']
    t.sync(A)
    t.ack(A, job_id, ok=False, error='x')
    t.sync(B, running(f'part-{job_id}.gcode.3mf'))
    assert t.get('a', '/printer/status').get_json()['last_result'] is not None
