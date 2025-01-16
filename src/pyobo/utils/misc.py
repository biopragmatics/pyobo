"""Miscellaneous utilities."""

import logging
from collections.abc import Callable
from datetime import datetime

import requests

from pyobo.constants import OBOFormats

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
}
STATIC_VERSION_REWRITES = {"orth": "2"}
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
]
VERSION_PREFIX_SPLITS = [
    "http://www.ebi.ac.uk/efo/releases/v",
    "http://www.ebi.ac.uk/swo/swo.owl/",
    "http://semanticscience.org/ontology/sio/v",
    "http://ontology.neuinfo.org/NIF/ttl/nif/version/",
]


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
    res = requests.get(url, stream=True)
    for i, line in enumerate(res.iter_lines(decode_unicode=True)):
        line = line.strip()
        if line.startswith("data-version"):
            return cleanup_version(line, prefix=prefix)
        if not line:
            return None
        if i > max_lines:
            return None
    return None


VERSION_IRI_TAG = "<owl:versionIRI rdf:resource="
VERSION_IRI_TAG_LEN = len(VERSION_IRI_TAG)


def _get_owl_version(prefix: str, url: str, *, max_lines: int = 200) -> str | None:
    res = requests.get(url, stream=True)
    for i, line in enumerate(res.iter_lines(decode_unicode=True)):
        line = line.strip()
        if line.startswith(VERSION_IRI_TAG):
            part = line[VERSION_IRI_TAG_LEN:].removesuffix("/>")
            return cleanup_version(part, prefix=prefix)
        if i > max_lines:
            return None
    return None


def _get_json_version(prefix: str, url: str) -> str | None:
    res = requests.get(url).json()
    version = res["graphs"][0]["meta"]["version"]
    return cleanup_version(version, prefix)


VERSION_GETTERS: dict[OBOFormats, Callable[[str, str], str | None]] = {
    "obo": _get_obo_version,
    "owl": _get_owl_version,
    "json": _get_json_version,
}
