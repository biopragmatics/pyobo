"""Conversion functionality between OFN and OBO."""

from .exporter import (
    get_ofn_from_obo,
    get_ontology_annotations,
    get_ontology_axioms,
    get_term_axioms,
    get_typedef_axioms,
)

__all__ = [
    "get_ofn_from_obo",
    "get_ontology_annotations",
    "get_ontology_axioms",
    "get_term_axioms",
    "get_typedef_axioms",
]
