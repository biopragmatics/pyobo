"""Reusable vocabulary."""

from __future__ import annotations

from .reference import Reference

__all__ = [
    "equivalent_class",
    "has_contributor",
    "mapping_has_confidence",
    "mapping_has_justification",
]

mapping_has_justification = Reference(
    prefix="sssom", identifier="mapping_justification", name="mapping justification"
)
mapping_has_confidence = Reference(prefix="sssom", identifier="confidence", name="has confidence")
has_contributor = Reference(prefix="dcterms", identifier="contributor", name="contributor")
has_dbxref = Reference(
    prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
)
equivalent_class = Reference(prefix="owl", identifier="equivalentClass", name="equivalent class")
term_replaced_by = Reference(prefix="IAO", identifier="0100001", name="term replaced by")
alternative_term = Reference(prefix="IAO", identifier="0000118", name="alternative term")
has_ontology_root_term = Reference(
    prefix="IAO", identifier="0000700", name="has ontology root term"
)
see_also = Reference(prefix="rdfs", identifier="seeAlso", name="see also")
comment = Reference(prefix="rdfs", identifier="comment", name="comment")

CHARLIE = Reference(prefix="orcid", identifier="0000-0003-4423-4370")

#: These are predicates that have their own dedicated fields
#: in OBO and FunOWL output
SKIP_PROPERTY_PREDICATES = {
    term_replaced_by,
    see_also,
    alternative_term,
}
