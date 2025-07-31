"""Constants for PyOBO."""

from __future__ import annotations

import logging
import re

import pystow
from typing_extensions import NotRequired, TypedDict

__all__ = [
    "DATABASE_DIRECTORY",
    "RAW_DIRECTORY",
    "SPECIES_REMAPPING",
]

logger = logging.getLogger(__name__)

PYOBO_MODULE = pystow.module("pyobo")
RAW_MODULE = PYOBO_MODULE.module("raw")
RAW_DIRECTORY = RAW_MODULE.base
DATABASE_MODULE = PYOBO_MODULE.module("database")
DATABASE_DIRECTORY = DATABASE_MODULE.base

#: The directory inside an ontology cache where
#: large artifacts like OBO, OWL, JSON, etc. go
BUILD_SUBDIRECTORY_NAME = "build"
#: The directory inside an ontology cache where
#: small caches for alts, xrefs, names, etc. go
CACHE_SUBDIRECTORY_NAME = "cache"
#: the directory for caching relations
RELATION_SUBDIRECTORY_NAME = "relations"

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

NCBITAXON_PREFIX = "ncbitaxon"
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


class DatabaseKwargs(TypedDict):
    """Keyword arguments for database CLI functions."""

    strict: bool
    force: bool
    force_process: bool
    skip_pyobo: bool
    skip_below: str | None
    skip_set: set[str] | None
    use_tqdm: bool


class SlimGetOntologyKwargs(TypedDict):
    """Keyword arguments for database CLI functions.

    These arguments are global during iteration over _all_ ontologies, whereas the
    additional ``version`` is added in the subclass below for specific instances when
    only a single ontology is requested.
    """

    strict: NotRequired[bool]
    force: NotRequired[bool]
    force_process: NotRequired[bool]


class GetOntologyKwargs(SlimGetOntologyKwargs):
    """Represents the optional keyword arguments passed to :func:`pyobo.get_ontology`.

    This dictionary doesn't contain ``prefix`` since this is always explicitly handled.
    """

    version: NotRequired[str | None]
    cache: NotRequired[bool]
    use_tqdm: NotRequired[bool]


def check_should_force(data: GetOntologyKwargs) -> bool:
    """Determine whether caching should be forced based on generic keyword arguments."""
    # note that this could be applied to the superclass of GetOntologyKwargs
    # but this function should only be used in the scope where GetOntologyKwargs
    # is appropriate.
    return data.get("force", False) or data.get("force_process", False)


def check_should_cache(data: GetOntologyKwargs) -> bool:
    """Determine whether caching should be done based on generic keyword arguments."""
    return data.get("cache", True)


def check_should_use_tqdm(data: GetOntologyKwargs) -> bool:
    """Determine whether caching should be done based on generic keyword arguments."""
    return data.get("use_tqdm", True)


class LookupKwargs(GetOntologyKwargs):
    """Represents all arguments passed to :func:`pyobo.get_ontology`.

    This dictionary does contain the ``prefix`` since it's used in the scope of CLI
    functions.
    """

    prefix: str


class IterHelperHelperDict(SlimGetOntologyKwargs):
    """Represents arguments needed when iterating over all ontologies.

    The explicitly defind arguments in this typed dict are used for the loop function
    :func:`iter_helper_helper` and the rest that are inherited get passed to
    :func:`pyobo.get_ontology` in each iteration.
    """

    use_tqdm: bool
    skip_below: str | None
    skip_pyobo: bool
    skip_set: set[str] | None


#: from table 2 of the Functional OWL syntax definition
#: at https://www.w3.org/TR/owl2-syntax/#IRIs
DEFAULT_PREFIX_MAP = {
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
}
