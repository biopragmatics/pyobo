# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import os

__all__ = [
    'PYOBO_HOME',
    'OUTPUT_DIRECTORY',
    'SPECIES_REMAPPING',
]

PYOBO_HOME = os.environ.get('PYOBO_HOME') or os.path.join(os.path.expanduser('~'), '.obo')

OUTPUT_DIRECTORY = (
    os.environ.get('PYOBO_OUTPUT')
    or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'obo'))
)

SPECIES_REMAPPING = {
    "Canis familiaris": "Canis lupus familiaris",
}

GLOBAL_SKIP = {
    'rnao',
    'mo',  # deprecated
    'resid',  # deprecated
    'adw',  # deprecated
}
