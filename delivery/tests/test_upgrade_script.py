"""The pieces of `make upgrade-printer-library` that need no network: finding and moving the
one pin, and refusing to go on when a patch is kept. (The whole command was run once,
2.6.6 to 2.6.5 and back; the result file records it.)"""
import importlib.util
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts',
                      'upgrade_printer_library.py')
spec = importlib.util.spec_from_file_location('upgrade_printer_library', SCRIPT)
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


def test_the_pin_is_found_and_moved_and_nothing_else_changes():
    text = 'dependencies = [\n    "bambulabs_api==1.2.3",\n    "requests==2.31.0",\n]\n'
    assert upgrade.current_pin(text) == '1.2.3'
    moved = upgrade.move_pin(text, '1.3.0')
    assert moved == text.replace('1.2.3', '1.3.0')


def test_the_librarys_own_dependencies_are_floated_then_pinned_to_the_lock():
    text = ('dependencies = [\n    "bambulabs_api==1.2.3",\n    "paho-mqtt==2.2.0",\n'
            '    "pillow==13.0.0",\n    "requests==2.31.0",\n]\n')
    floated = upgrade.float_followers(text)
    assert '"paho-mqtt",' in floated and '"pillow",' in floated
    assert '"requests==2.31.0"' in floated
    pinned = upgrade.pin_followers(floated, {'paho-mqtt': '2.3.0', 'pillow': '13.0.0'})
    assert pinned == text.replace('paho-mqtt==2.2.0', 'paho-mqtt==2.3.0')


def test_the_pins_the_shop_computer_installs_are_the_locked_versions():
    """Defect 9: pip on the shop computer reads daemon/pyproject.toml, not uv.lock, so the
    library's own dependencies are pinned there to what the upstream check ran on."""
    with open(upgrade.PYPROJECT, encoding='utf-8') as fh:
        text = fh.read()
    locked = upgrade.locked_versions()
    for name in upgrade.FOLLOWERS:
        assert f'"{name}=={locked[name]}"' in text, name


def test_no_pin_is_a_clear_stop():
    with pytest.raises(SystemExit, match='no bambulabs_api pin'):
        upgrade.current_pin('dependencies = []')


def test_patches_are_found_per_version(tmp_path):
    assert upgrade.patches_for('1.0', folder=str(tmp_path / 'none')) == ([], [])
    (tmp_path / '1.0').mkdir()
    (tmp_path / '1.0' / 'fix-log.patch').write_text('x')
    (tmp_path / '1.0' / 'NOTE.md').write_text('x')
    assert upgrade.patches_for('1.0', folder=str(tmp_path)) == (['fix-log.patch'], ['1.0'])
    assert upgrade.patches_for('2.0', folder=str(tmp_path)) == ([], ['1.0'])


def test_a_malformed_version_is_refused_before_anything_changes(capsys):
    assert upgrade.main(['not a version']) == 2
    assert upgrade.main([]) == 2


def test_the_pin_file_holds_one_pin_today():
    with open(upgrade.PYPROJECT, encoding='utf-8') as fh:
        assert upgrade.current_pin(fh.read())
    assert upgrade.patches_for(upgrade.current_pin(open(upgrade.PYPROJECT).read())) == ([], [])
