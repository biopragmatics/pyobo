# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import json
import logging
import os
import re

import pystow

__all__ = [
    "RAW_DIRECTORY",
    "DATABASE_DIRECTORY",
    "SPECIES_REMAPPING",
    "VERSION_PINS",
]


logger = logging.getLogger(__name__)

PYOBO_MODULE = pystow.module("pyobo")
RAW_MODULE = PYOBO_MODULE.module("raw")
RAW_DIRECTORY = RAW_MODULE.base
DATABASE_MODULE = PYOBO_MODULE.module("database")
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

#: Default prefix
DEFAULT_PREFIX = "debio"
DEFAULT_PATTERN = re.compile("^\\d{7}$")

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
TYPEDEFS_FILE = "typedefs.tsv.gz"

SPECIES_RECORD = "5334738"
SPECIES_FILE = "species.tsv.gz"

NCBITAXON_PREFIX = "NCBITaxon"
DATE_FORMAT = "%d:%m:%Y %H:%M"
PROVENANCE_PREFIXES = {
    "pubmed",
    "pmc",
    "doi",
    "biorxiv",
    "chemrxiv",
    "wikipedia",
    "google.patent",
    "agricola",
    "cba",
    "ppr",
    "citexplore",
    "goc",
    "isbn",
    "issn",
}

# Load version pin dictionary from the environmental variable VERSION_PINS
try:
    VERSION_PINS_STR = os.getenv("VERSION_PINS")
    if not VERSION_PINS_STR:
        VERSION_PINS = {}
    else:
        VERSION_PINS = json.loads(VERSION_PINS_STR)
        invalid_prefixes = []
        for prefix, version in VERSION_PINS.items():
            if not isinstance(prefix, str) or not isinstance(version, str):
                logger.error(f"The prefix:{prefix} and version:{version} name must both be strings")
                invalid_prefixes.append(prefix)
        for prefix in invalid_prefixes:
            VERSION_PINS.pop(prefix)
except ValueError as e:
    logger.error(
        "The value for the environment variable VERSION_PINS must be a valid JSON string: %s" % e
    )
    VERSION_PINS = {}

if VERSION_PINS:
    logger.debug(
        f"These are the resource versions that are pinned.\n{VERSION_PINS}. "
        f"\nPyobo will download the latest version of a resource if it's "
        f"not pinned.\nIf you want to use a specific version of a "
        f"resource, edit your VERSION_PINS environmental "
        f"variable which is a JSON string to include a prefix and version "
        f"name."
    )
