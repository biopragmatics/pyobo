# -*- coding: utf-8 -*-

"""Miscellaneous utilities."""

import gzip

__all__ = [
    "obo_to_obograph",
]


def obo_to_obograph(obo_path, obograph_path) -> None:
    """Convert an OBO file to OBO Graph file with pronto."""
    import pronto

    ontology = pronto.Ontology(obo_path)
    with gzip.open(obograph_path, "wb") as file:
        ontology.dump(file, format="json")
