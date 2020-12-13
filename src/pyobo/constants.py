# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import configparser
import logging
import os
from functools import partial
from typing import Callable

import bioversions
import pystow

__all__ = [
    'PYOBO_HOME',
    'RAW_DIRECTORY',
    'DATABASE_DIRECTORY',
    'SPECIES_REMAPPING',
    'get_sqlalchemy_uri',
    'version_getter',
]

logger = logging.getLogger(__name__)

if 'PYOBO_CONFIG' in os.environ:
    PYOBO_CONFIG = os.environ['PYOBO_CONFIG']
else:
    _config_dir = os.path.join(os.path.expanduser('~'), '.config')
    os.makedirs(_config_dir, exist_ok=True)
    PYOBO_CONFIG = os.path.join(_config_dir, 'pyobo.ini')

PYOBO_MODULE = pystow.Module.from_key('pyobo')
PYOBO_HOME = PYOBO_MODULE.base
RAW_MODULE = PYOBO_MODULE.submodule('raw')
RAW_DIRECTORY = RAW_MODULE.base
DATABASE_DIRECTORY = PYOBO_MODULE.get('database')


def get_raw(*parts, **kwargs):
    # TODO replace with module!!
    return pystow.get('pyobo', 'raw', *parts, **kwargs)


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
INSPECTOR_JAVERT_URL = 'https://zenodo.org/record/4021477/files/xrefs.tsv.gz'
SOURCE_PREFIX = 'source_ns'
SOURCE_ID = 'source_id'
RELATION_PREFIX = 'relation_ns'
RELATION_ID = 'relation_id'
TARGET_PREFIX = 'target_ns'
TARGET_ID = 'target_id'
PROVENANCE = 'source'
RELATION_COLUMNS = [SOURCE_PREFIX, SOURCE_ID, RELATION_PREFIX, RELATION_ID, TARGET_PREFIX, TARGET_ID]
XREF_COLUMNS = [SOURCE_PREFIX, SOURCE_ID, TARGET_PREFIX, TARGET_ID, PROVENANCE]

#: URL for the nomenclature data that's pre-cached
OOH_NA_NA_URL = 'https://zenodo.org/record/4020486/files/names.tsv.gz'

SYNONYMS_URL = 'https://zenodo.org/record/4021482/files/synonyms.tsv.gz'

REMOTE_ALT_DATA_URL = 'https://zenodo.org/record/4021476/files/alts.tsv.gz'


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

    default_db_path = (PYOBO_HOME / 'pyobo.db').as_posix()
    return f'sqlite:///{default_db_path}'


def version_getter(name: str) -> Callable[[], str]:
    """Make a function appropriate for getting versions."""
    return partial(bioversions.get_version, name)
