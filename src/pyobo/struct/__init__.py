"""Data structures for OBO."""

from .reference import Reference, Referenced, default_reference
from .struct import (
    Obo,
    Synonym,
    SynonymTypeDef,
    Term,
    int_identifier_sort_key,
    make_ad_hoc_ontology,
)
from .typedef import (
    TypeDef,
    derives_from,
    enables,
    from_species,
    gene_product_member_of,
    has_category,
    has_gene_product,
    has_member,
    has_part,
    has_participant,
    is_a,
    member_of,
    orthologous,
    part_of,
    participates_in,
    species_specific,
    superclass_of,
    transcribes_to,
    translates_to,
)

__all__ = [
    "Obo",
    "Reference",
    "Referenced",
    "Synonym",
    "SynonymTypeDef",
    "Term",
    "TypeDef",
    "default_reference",
    "derives_from",
    "enables",
    "from_species",
    "gene_product_member_of",
    "has_category",
    "has_gene_product",
    "has_member",
    "has_part",
    "has_participant",
    "int_identifier_sort_key",
    "is_a",
    "make_ad_hoc_ontology",
    "member_of",
    "orthologous",
    "part_of",
    "participates_in",
    "species_specific",
    "superclass_of",
    "transcribes_to",
    "translates_to",
]
