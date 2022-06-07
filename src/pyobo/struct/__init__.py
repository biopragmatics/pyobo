# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from .reference import Reference  # noqa: F401
from .struct import (  # noqa: F401
    Obo,
    Synonym,
    SynonymTypeDef,
    Term,
    make_ad_hoc_ontology,
)
from .typedef import (  # noqa: F401
    RelationHint,
    TypeDef,
    from_species,
    gene_product_member_of,
    get_reference_tuple,
    has_gene_product,
    has_member,
    has_part,
    is_a,
    member_of,
    orthologous,
    part_of,
    species_specific,
    superclass_of,
    transcribes_to,
    translates_to,
)
