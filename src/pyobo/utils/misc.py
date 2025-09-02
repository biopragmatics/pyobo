"""Miscellaneous utilities."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime

import bioversions.utils

from pyobo.constants import ONTOLOGY_GETTERS, OntologyFormat

__all__ = [
    "VERSION_GETTERS",
    "cleanup_version",
]

logger = logging.getLogger(__name__)

BIZARRE_LOGGED = set()

#: Rewrites for mostly static resources that have weird quirks
VERSION_REWRITES = {
    "$Date: 2009/11/15 10:54:12 $": "2009-11-15",  # for owl
    "http://www.w3.org/2006/time#2016": "2016",  # for time
    "https://purl.org/ontology/modalia#1.0.0": "1.0.0",  # for dalia
}
STATIC_VERSION_REWRITES = {
    "orth": "2",
}
VERSION_PREFIXES = [
    "http://www.orpha.net/version",
    "https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_",
    "http://humanbehaviourchange.org/ontology/bcio.owl/",
    "http://purl.org/pav/",
    "http://identifiers.org/combine.specifications/teddy.rel-",
    "https://purl.dataone.org/odo/MOSAIC/",
    "http://purl.dataone.org/odo/SASAP/",  # like in http://purl.dataone.org/odo/SASAP/0.3.1
    "http://purl.dataone.org/odo/SENSO/",  # like in http://purl.dataone.org/odo/SENSO/0.1.0
    "https://purl.dataone.org/odo/ADCAD/",
    "http://identifiers.org/combine.specifications/teddy.rel-",
    "https://nfdi.fiz-karlsruhe.de/ontology/",
    "http://www.w3.org/ns/prov-",
    "https://raw.githubusercontent.com/enpadasi/Ontology-for-Nutritional-Studies/releases/download/v",
    "http://purl.jp/bio/4/ontology/iobc/",  # like http://purl.jp/bio/4/ontology/iobc/1.6.0
    "http://w3id.org/nfdi4ing/metadata4ing/",  # like http://w3id.org/nfdi4ing/metadata4ing/1.3.1
    "http://www.semanticweb.com/OntoRxn/",  # like http://www.semanticweb.com/OntoRxn/0.2.5
    "https://w3id.org/lehrplan/ontology/",  # like in https://w3id.org/lehrplan/ontology/1.0.0-4
    "http://www.ebi.ac.uk/swo/version/",  # http://www.ebi.ac.uk/swo/version/6.0
    "https://w3id.org/emi/version/",
]
VERSION_PREFIX_SPLITS = [
    "http://www.ebi.ac.uk/efo/releases/v",
    "http://www.ebi.ac.uk/swo/swo.owl/",
    "http://semanticscience.org/ontology/sio/v",
    "http://ontology.neuinfo.org/NIF/ttl/nif/version/",
    "http://nmrml.org/cv/v",  # as in http://nmrml.org/cv/v1.1.0/nmrCV
    "http://enanomapper.github.io/ontologies/releases/",  # as in http://enanomapper.github.io/ontologies/releases/10.0/enanomapper
]
BAD = {
    "http://purl.obolibrary.org/obo",
    "http://www.bioassayontology.org/bao/bao_complete",
}


def cleanup_version(data_version: str, prefix: str) -> str:
    """Clean the version information."""
    # in case a literal string that wasn't parsed properly gets put in
    data_version = data_version.strip('"')

    if data_version in VERSION_REWRITES:
        return VERSION_REWRITES[data_version]

    data_version = data_version.removesuffix(".owl")
    if data_version.endswith(prefix):
        data_version = data_version[: -len(prefix)]
    data_version = data_version.removesuffix("/")

    data_version = data_version.removeprefix("releases/")
    data_version = data_version.removeprefix("release/")

    for version_prefix in VERSION_PREFIXES:
        if data_version.startswith(version_prefix):
            return data_version.removeprefix(version_prefix)

    for version_prefix_split in VERSION_PREFIX_SPLITS:
        if data_version.startswith(version_prefix_split):
            return data_version.removeprefix(version_prefix_split).split("/")[0]

    # use a heuristic to determine if the version is one of
    # consecutive, major.minor, or semantic versioning (i.e., major.minor.patch)
    if data_version.replace(".", "").isnumeric():
        return data_version

    for v in reversed(data_version.split("/")):
        v = v.strip()
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            continue
        else:
            return v
    if (prefix, data_version) not in BIZARRE_LOGGED:
        logger.debug("[%s] bizarre version: %s", prefix, data_version)
        BIZARRE_LOGGED.add((prefix, data_version))
    return data_version


def _get_obo_version(prefix: str, url: str, *, max_lines: int = 200) -> str | None:
    rv = bioversions.utils.get_obo_version(url, max_lines=max_lines)
    if rv is None:
        return None
    return cleanup_version(rv, prefix)


def _get_owl_version(prefix: str, url: str, *, max_lines: int = 200) -> str | None:
    rv = bioversions.utils.get_owl_xml_version(url, max_lines=max_lines)
    if rv is None:
        return None
    return cleanup_version(rv, prefix)


def _get_obograph_json_version(prefix: str, url: str) -> str | None:
    rv = bioversions.utils.get_obograph_json_version(url)
    if rv is None:
        return None
    return cleanup_version(rv, prefix)


#: A mapping from data type to gersion getter function
VERSION_GETTERS: dict[OntologyFormat, Callable[[str, str], str | None]] = {
    "obo": _get_obo_version,
    "owl": _get_owl_version,
    "json": _get_obograph_json_version,
}


def _prioritize_version(
    data_version: str | None,
    ontology_prefix: str,
    version: str | None,
    date: datetime | None,
) -> str | None:
    """Process version information coming from several sources and normalize them."""
    if ontology_prefix in STATIC_VERSION_REWRITES:
        return STATIC_VERSION_REWRITES[ontology_prefix]

    if version:
        if version in BAD:
            logger.debug("[%s] had known bad version, returning None: ", ontology_prefix, version)
            return None

        clean_injected_version = cleanup_version(version, prefix=ontology_prefix)
        if not data_version:
            logger.debug(
                "[%s] did not have a version, overriding with %s",
                ontology_prefix,
                clean_injected_version,
            )
            return clean_injected_version

        clean_data_version = cleanup_version(data_version, prefix=ontology_prefix)
        if clean_data_version != clean_injected_version:
            # in this case, we're going to trust the one that's passed
            # through explicitly more than the graph's content
            logger.debug(
                "[%s] had version %s, overriding with %s",
                ontology_prefix,
                data_version,
                version,
            )
        return clean_injected_version

    if data_version:
        if data_version in BAD:
            logger.debug(
                "[%s] had known bad version, returning None: ", ontology_prefix, data_version
            )
            return None

        clean_data_version = cleanup_version(data_version, prefix=ontology_prefix)
        logger.debug("[%s] using version %s", ontology_prefix, clean_data_version)
        return clean_data_version

    if date is not None:
        derived_date_version = date.strftime("%Y-%m-%d")
        logger.debug(
            "[%s] does not report a version. falling back to date: %s",
            ontology_prefix,
            derived_date_version,
        )
        return derived_date_version

    logger.debug("[%s] does not report a version nor a date", ontology_prefix)
    return None


def _get_getter_urls(prefix: str) -> Iterable[tuple[OntologyFormat, str]]:
    # assume that all possible files that can be downloaded
    # are in sync and have the same version
    for ontology_format, get_url_func in ONTOLOGY_GETTERS:
        url = get_url_func(prefix)
        if url is None:
            continue
        yield ontology_format, url


def _get_version_from_artifact(prefix: str) -> str | None:
    for ontology_format, url in _get_getter_urls(prefix):
        # Try to peak into the file to get the version without fully downloading
        get_version_func = VERSION_GETTERS.get(ontology_format)
        if get_version_func is None:
            continue
        version = get_version_func(prefix, url)
        if version:
            return cleanup_version(version, prefix=prefix)
    return None
