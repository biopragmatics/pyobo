# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from .reference import Reference  # noqa: F401
from .struct import Obo, Synonym, SynonymTypeDef, Term  # noqa: F401
from .typedef import (  # noqa: F401
    TypeDef, from_species, gene_product_is_a, get_reference_tuple, has_gene_product, has_member, has_part, is_a,
    part_of, subclass, transcribes_to, translates_to,
)
