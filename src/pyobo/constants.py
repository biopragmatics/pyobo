# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import configparser
import logging
import os

__all__ = [
    'PYOBO_HOME',
    'RAW_DIRECTORY',
    'DATABASE_DIRECTORY',
    'SPECIES_REMAPPING',
    'get_sqlalchemy_uri',
]

logger = logging.getLogger(__name__)

if 'PYOBO_CONFIG' in os.environ:
    PYOBO_CONFIG = os.environ['PYOBO_CONFIG']
else:
    _config_dir = os.path.join(os.path.expanduser('~'), '.config')
    os.makedirs(_config_dir, exist_ok=True)
    PYOBO_CONFIG = os.path.join(_config_dir, 'pyobo.ini')

PYOBO_HOME = os.environ.get('PYOBO_HOME') or os.path.join(os.path.expanduser('~'), '.obo')
RAW_DIRECTORY = os.path.join(PYOBO_HOME, 'raw')
os.makedirs(RAW_DIRECTORY, exist_ok=True)
DATABASE_DIRECTORY = os.path.join(PYOBO_HOME, 'database')
os.makedirs(DATABASE_DIRECTORY, exist_ok=True)

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
SOURCE_PREFIX = 'source_ns'
SOURCE_ID = 'source_id'
RELATION_PREFIX = 'relation_ns'
RELATION_ID = 'relation_id'
TARGET_PREFIX = 'target_ns'
TARGET_ID = 'target_id'
PROVENANCE = 'source'
XREF_COLUMNS = [SOURCE_PREFIX, SOURCE_ID, TARGET_PREFIX, TARGET_ID, PROVENANCE]

#: URL for the nomenclature data that's pre-cached
OOH_NA_NA_URL = 'https://zenodo.org/record/3866538/files/ooh_na_na.tsv.gz'

SYNONYMS_URL = 'https://zenodo.org/record/3893085/files/synonyms.tsv.gz'

REMOTE_ALT_DATA_URL = 'https://zenodo.org/record/4013858/files/pyobo_alts.tsv.gz'


def get_sqlalchemy_uri() -> str:
    """Get the SQLAlchemy URI."""
    if os.path.exists(PYOBO_CONFIG):
        cfp = configparser.ConfigParser()
        logger.debug('reading configuration from %s', PYOBO_CONFIG)
        with open(PYOBO_CONFIG) as file:
            cfp.read_file(file)
        rv = cfp.get('pyobo', 'SQLALCHEMY_URI')
        if rv:
            return rv

    rv = os.environ.get('PYOBO_SQLALCHEMY_URI')
    if rv is not None:
        return rv

    os.makedirs(PYOBO_HOME, exist_ok=True)
    default_db_path = os.path.abspath(os.path.join(PYOBO_HOME, 'pyobo.db'))
    return f'sqlite:///{default_db_path}'
