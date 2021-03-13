# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import logging
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

PYOBO_MODULE = pystow.Module.from_key('pyobo')
PYOBO_HOME = PYOBO_MODULE.base
RAW_MODULE = PYOBO_MODULE.submodule('raw')
RAW_DIRECTORY = RAW_MODULE.base
DATABASE_DIRECTORY = PYOBO_MODULE.get('database')

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
    default_db_path = (PYOBO_HOME / 'pyobo.db').as_posix()
    default_value = f'sqlite:///{default_db_path}'
    return pystow.get_config('pyobo', 'sqlalchemy_uri', fallback=default_value)


def version_getter(name: str) -> Callable[[], str]:
    """Make a function appropriate for getting versions."""
    return partial(bioversions.get_version, name)
