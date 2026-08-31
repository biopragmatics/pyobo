"""Conversion functionality between OFN and OBO."""

from .exporter import (
    get_ofn_from_obo,
    get_ontology_annotations,
    get_ontology_axioms,
    get_term_axioms,
    get_typedef_axioms,
)
from .importer import get_obo_from_ofn

__all__ = [
    "get_obo_from_ofn",
    "get_ofn_from_obo",
    "get_ontology_annotations",
    "get_ontology_axioms",
    "get_term_axioms",
    "get_typedef_axioms",
]
