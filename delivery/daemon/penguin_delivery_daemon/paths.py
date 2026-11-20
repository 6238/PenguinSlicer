"""Where the daemon keeps everything: the one module that decides.

The daemon is a plain Python program that runs wherever Python does (Windows, macOS,
Linux). Its configuration, its state and its downloads live in ONE directory, the daemon's
home, which the person running it chooses with `--home DIR`. Without the option:

| Platform | Default home |
|---|---|
| Windows | `%LOCALAPPDATA%\\PenguinDelivery`, else `~\\PenguinDelivery` |
| macOS, Linux and anything else | `~/.penguin-delivery` |

Inside it: `config.toml` (the pairing, the printer's address and access code, the token),
`downloads/` (a sliced file on its way to the printer, removed once sent) and
`recordings/` (what `record` saves).

The platform and the environment are arguments, so the tests choose each platform's answer
on any machine.
"""

import os
import sys
from dataclasses import dataclass

#: Where the installer of the earlier version put the configuration. Only an install made
#: by that installer (daemon/install.sh, not maintained in this version) uses it.
LEGACY_CONFIG_PATH = '/etc/penguincam-printer/config.toml'


def default_home(*, platform=None, environ=None, expanduser=os.path.expanduser):
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if platform.startswith('win'):
        base = environ.get('LOCALAPPDATA') or expanduser('~')
        return os.path.join(base, 'PenguinDelivery')
    return os.path.join(expanduser('~'), '.penguin-delivery')


@dataclass(frozen=True)
class DaemonHome:
    root: str

    @property
    def config(self):
        return os.path.join(self.root, 'config.toml')

    @property
    def downloads(self):
        return os.path.join(self.root, 'downloads')

    @property
    def recordings(self):
        return os.path.join(self.root, 'recordings')


def home_for(home=None, config=None, **platform_args):
    """The DaemonHome for `--home` (or the default). A `--config FILE` given instead puts
    the home in that file's directory, so everything still lives together."""
    if home:
        return DaemonHome(os.path.abspath(home))
    if config:
        return DaemonHome(os.path.dirname(os.path.abspath(config)))
    return DaemonHome(default_home(**platform_args))


def is_service_install(config_path, *, platform=None):
    """True only for a Linux install made by the earlier installer, where `pair` still
    hands the file to the service user and restarts the service. Never on Windows or
    macOS, and never for a home the person chose."""
    platform = sys.platform if platform is None else platform
    return platform.startswith('linux') and os.path.abspath(config_path) == LEGACY_CONFIG_PATH
