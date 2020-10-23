# -*- coding: utf-8 -*-

"""Get PyOBO configuration."""

import configparser
import os
from functools import lru_cache
from typing import Optional

__all__ = [
    'get_config',
]


@lru_cache()
def _get_configparser() -> Optional[configparser.ConfigParser]:
    cfp = configparser.ConfigParser()
    cfp.read([
        os.path.join(os.path.expanduser('~'), '.config', 'pyobo.ini'),
        os.path.join(os.path.expanduser('~'), '.config', 'pyobo.cfg'),
        os.path.join(os.path.expanduser('~'), '.config', 'pyobo', 'config.ini'),
    ])
    if cfp.has_section('pyobo'):
        return cfp


def get_config(key: str) -> str:
    """Get configuration.

    :raises: FileNotFoundError
    :raises: configparser.NoOptionError
    """
    cfp = _get_configparser()
    if cfp:
        return cfp.get('pyobo', key)

    raise FileNotFoundError('Missing config at ~/.config/pyobo.ini')


if __name__ == '__main__':
    get_config('adgag')
