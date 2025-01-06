"""Reusable vocabulary."""

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
