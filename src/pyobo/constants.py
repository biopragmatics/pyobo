# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import os

__all__ = [
    'PYOBO_HOME',
    'OUTPUT_DIRECTORY',
    'SPECIES_REMAPPING',
]

if 'PYOBO_CONFIG' in os.environ:
    PYOBO_CONFIG = os.environ['PYOBO_CONFIG']
else:
    _config_dir = os.path.join(os.path.expanduser('~'), '.config')
    os.makedirs(_config_dir, exist_ok=True)
    PYOBO_CONFIG = os.path.join(_config_dir, 'pyobo.ini')

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

#: URL for the xref data that's pre-cached
INSPECTOR_JAVERT_URL = 'https://zenodo.org/record/3757266/files/inspector_javerts_xrefs.tsv.gz'

#: URL for the nomenclature data that's pre-cached
OOH_NA_NA_URL = 'https://zenodo.org/record/3866538/files/ooh_na_na.tsv.gz'

SYNONYMS_URL = 'https://zenodo.org/record/3893085/files/synonyms.tsv.gz'

REMOTE_ALT_DATA_URL = 'https://zenodo.org/record/4013858/files/pyobo_alts.tsv.gz'
