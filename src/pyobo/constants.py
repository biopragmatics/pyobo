# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import os

__all__ = [
    'PYOBO_HOME',
    'OUTPUT_DIRECTORY',
    'CURATED_URLS',
]

PYOBO_HOME = os.environ.get('PYOBO_HOME') or os.path.join(os.path.expanduser('~'), '.obo')

OUTPUT_DIRECTORY = (
    os.environ.get('PYOBO_OUTPUT')
    or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'obo'))
)

#: A curated list of prefixes to URLs for OBO files that aren't properly listed in OBO Foundry
CURATED_URLS = {
    'mp': 'http://purl.obolibrary.org/obo/mp.obo',
    'chiro': 'http://purl.obolibrary.org/obo/chiro.obo',
}
