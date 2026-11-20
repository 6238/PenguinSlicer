"""Review 4, defect 5: the pieces of "Try it on one machine" that the suites can check
without sockets: the relay on its own, the printer ports in the daemon's configuration,
and `pair --printer-ports`."""

import io
import os

import pytest

from penguin_delivery_daemon import __main__ as cli
from penguin_delivery_daemon import config as cfg

from together import relay_server


def test_the_relay_on_its_own_pairs_signs_in_and_names_the_sample(tmp_path):
    out = io.StringIO()
    sample = tmp_path / 'part.gcode.3mf'
    sample.write_bytes(b'3mf')
    app, _log = relay_server.build('7K3M-Q9XW', str(sample), out=out)
    client = app.test_client()
    status = client.get('/printer/status').get_json()
    assert status['paired'] is True and status['code'] == '7K3M-Q9XW'
    # Development mode: plain HTTP pairing, and the seeded code is presented already.
    token = client.post('/printer/daemon/pair', json={'code': '7K3MQ9XW'}).get_json()
    assert token.get('token')
    assert 'request=pair' in out.getvalue() and '7K3MQ9XW' not in out.getvalue()


@pytest.mark.parametrize('text,expected', [(None, (0, 0)), ('', (0, 0)),
                                           ('18883,18990', (18883, 18990)),
                                           (' 1 , 65535 ', (1, 65535))])
def test_printer_ports_are_read(text, expected):
    assert cli.parse_printer_ports(text) == expected


@pytest.mark.parametrize('text', ['18883', '1,2,3', 'a,b', '0,990', '8883,70000', '-1,2'])
def test_bad_printer_ports_are_refused(text):
    with pytest.raises(ValueError, match='MQTT,FTPS'):
        cli.parse_printer_ports(text)


def test_pair_refuses_bad_printer_ports_before_asking_anything(tmp_path):
    out = io.StringIO()
    args = cli.build_parser().parse_args(['pair', '--home', str(tmp_path),
                                          '--printer-ports', 'nonsense'])
    assert cli.cmd_pair(args, ask=lambda: pytest.fail('asked'), out=out) == 2
    assert '--printer-ports takes two port numbers' in out.getvalue()


def test_printer_ports_are_kept_in_the_configuration_only_when_set(tmp_path):
    path = os.path.join(tmp_path, 'config.toml')
    cfg.save_config(cfg.DaemonConfig(printer_ip='127.0.0.1', path=path))
    with open(path, encoding='utf-8') as fh:
        assert 'port' not in fh.read()
    assert cfg.load_config(path).printer_ports() is None
    cfg.save_config(cfg.DaemonConfig(printer_ip='127.0.0.1', printer_mqtt_port=18883,
                                     printer_ftps_port=18990, path=path))
    assert cfg.load_config(path).printer_ports() == {'mqtt': 18883, 'ftps': 18990}


def test_a_hand_edited_port_that_is_not_a_port_is_the_printers_own(tmp_path):
    path = os.path.join(tmp_path, 'config.toml')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('printer_ip = "127.0.0.1"\nprinter_mqtt_port = "18883"\n'
                 'printer_ftps_port = 99999\n')
    assert cfg.load_config(path).printer_ports() is None
