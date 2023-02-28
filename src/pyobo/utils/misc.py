# -*- coding: utf-8 -*-

"""Miscellaneous utilities."""

import gzip
import logging
import os
from datetime import datetime
from subprocess import check_output  # noqa:S404
from typing import Optional

__all__ = [
    "obo_to_obograph",
    "obo_to_owl",
    "cleanup_version",
]


logger = logging.getLogger(__name__)


def obo_to_obograph(obo_path, obograph_path) -> None:
    """Convert an OBO file to OBO Graph file with pronto."""
    import pronto

    ontology = pronto.Ontology(obo_path)
    with gzip.open(obograph_path, "wb") as file:
        ontology.dump(file, format="json")


def obo_to_owl(obo_path, owl_path, owl_format: str = "ofn"):
    """Convert an OBO file to an OWL file with ROBOT."""
    args = ["robot", "convert", "-i", obo_path, "-o", owl_path, "--format", owl_format]
    ret = check_output(  # noqa:S603
        args,
        cwd=os.path.dirname(__file__),
    )
    return ret.decode()


BIZARRE_LOGGED = set()


def cleanup_version(data_version: str, prefix: str) -> Optional[str]:
    """Clean the version information."""
    if data_version.endswith(".owl"):
        data_version = data_version[: -len(".owl")]
    if data_version.endswith(prefix):
        data_version = data_version[: -len(prefix)]
    if data_version.startswith("releases/"):
        data_version = data_version[len("releases/") :]
    if prefix == "orth":
        # TODO add bioversions for this
        return "2"
    if data_version.startswith("http://www.orpha.net/version"):
        return data_version[len("http://www.orpha.net/version") :]
    if data_version.startswith("http://humanbehaviourchange.org/ontology/bcio.owl/"):
        return data_version[len("http://humanbehaviourchange.org/ontology/bcio.owl/") :]
    if data_version.startswith("http://www.ebi.ac.uk/efo/releases/v"):
        return data_version[len("http://www.ebi.ac.uk/efo/releases/v") :].split("/")[0]
    if data_version.startswith("http://www.ebi.ac.uk/swo/swo.owl/"):
        return data_version[len("http://www.ebi.ac.uk/swo/swo.owl/") :].split("/")[0]
    if data_version.startswith("http://purl.org/pav/"):
        return data_version[len("http://purl.org/pav/") :]
    if data_version.startswith("http://semanticscience.org/ontology/sio/v"):
        return data_version[len("http://semanticscience.org/ontology/sio/v")].split("/")[0]
    if data_version.startswith("http://ontology.neuinfo.org/NIF/ttl/nif/version/"):
        return data_version[len("http://ontology.neuinfo.org/NIF/ttl/nif/version/") :].split("/")[0]
    if data_version.startswith("http://identifiers.org/combine.specifications/teddy.rel-"):
        return data_version[len("http://identifiers.org/combine.specifications/teddy.rel-") :]
    if data_version.replace(".", "").isnumeric():
        return data_version  # consecutive, major.minor, or semantic versioning
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
