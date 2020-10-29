# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from .reference import Reference  # noqa: F401
from .struct import Obo, Synonym, SynonymTypeDef, Term  # noqa: F401
from .typedef import (  # noqa: F401
    TypeDef, TypeDef, TypeDef, from_species, from_species, from_species, gene_product_is_a,
    gene_product_is_a, get_reference_tuple, get_reference_tuple, get_reference_tuple, has_gene_product,
    has_gene_product, has_member, has_member, has_member, has_part, has_part, has_part, is_a, is_a, part_of, part_of,
    part_of, subclass, subclass, subclass, transcribes_to, translates_to,
)
