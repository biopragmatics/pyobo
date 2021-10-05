# -*- coding: utf-8 -*-

"""Miscellaneous utilities."""

import gzip
import os
from subprocess import check_output  # noqa:S404

__all__ = [
    "obo_to_obograph",
    "obo_to_owl",
]


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
