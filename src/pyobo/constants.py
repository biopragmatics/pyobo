# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import logging
from functools import partial
from typing import Callable

import bioversions
import pystow

__all__ = [
    "RAW_DIRECTORY",
    "DATABASE_DIRECTORY",
    "SPECIES_REMAPPING",
    "get_sqlalchemy_uri",
    "version_getter",
]

logger = logging.getLogger(__name__)

PYOBO_MODULE = pystow.module("pyobo")
RAW_MODULE = PYOBO_MODULE.submodule("raw")
RAW_DIRECTORY = RAW_MODULE.base
DATABASE_MODULE = PYOBO_MODULE.submodule("database")
DATABASE_DIRECTORY = DATABASE_MODULE.base

SPECIES_REMAPPING = {
    "Canis familiaris": "Canis lupus familiaris",
}

GLOBAL_SKIP = {
    "rnao",
    "mo",  # deprecated
    "resid",  # deprecated
    "adw",  # deprecated
}

SOURCE_PREFIX = "source_ns"
SOURCE_ID = "source_id"
RELATION_PREFIX = "relation_ns"
RELATION_ID = "relation_id"
TARGET_PREFIX = "target_ns"
TARGET_ID = "target_id"
PROVENANCE = "source"
RELATION_COLUMNS = [
    SOURCE_PREFIX,
    SOURCE_ID,
    RELATION_PREFIX,
    RELATION_ID,
    TARGET_PREFIX,
    TARGET_ID,
]
XREF_COLUMNS = [SOURCE_PREFIX, SOURCE_ID, TARGET_PREFIX, TARGET_ID, PROVENANCE]

JAVERT_RECORD = "4021477"
JAVERT_FILE = "xrefs.tsv.gz"

OOH_NA_NA_RECORD = "4020486"
OOH_NA_NA_FILE = "names.tsv.gz"

SYNONYMS_RECORD = "4021482"
SYNONYMS_FILE = "synonyms.tsv.gz"

RELATIONS_RECORD = "4625167"
RELATIONS_FILE = "relations.tsv.gz"

PROPERTIES_RECORD = "4625172"
PROPERTIES_FILE = "properties.tsv.gz"

ALTS_DATA_RECORD = "4021476"
ALTS_FILE = "alts.tsv.gz"

DEFINITIONS_RECORD = "4637061"
DEFINITIONS_FILE = "definitions.tsv.gz"

TYPEDEFS_RECORD = "4644013"
TYPEDEFS_FILE = "typedefs.tzv.gz"

REFS_TABLE_NAME = "obo_reference"
ALTS_TABLE_NAME = "obo_alt"
DEFS_TABLE_NAME = "obo_def"


def get_sqlalchemy_uri() -> str:
    """Get the SQLAlchemy URI."""
    rv = pystow.get_config("pyobo", "sqlalchemy_uri")
    if rv is not None:
        return rv

    default_db_path = PYOBO_MODULE.join("pyobo.db")
    default_value = f"sqlite:///{default_db_path.as_posix()}"
    return default_value


def version_getter(name: str) -> Callable[[], str]:
    """Make a function appropriate for getting versions."""
    return partial(bioversions.get_version, name)
