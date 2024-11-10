"""Data structures for OBO."""

from .reference import Reference, Referenced  # noqa: F401
from .struct import (  # noqa: F401
    Obo,
    Synonym,
    SynonymSpecificities,
    SynonymSpecificity,
    SynonymTypeDef,
    Term,
    int_identifier_sort_key,
    make_ad_hoc_ontology,
)
from .typedef import (  # noqa: F401
    TypeDef,
    derives_from,
    enables,
    from_species,
    gene_product_member_of,
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
