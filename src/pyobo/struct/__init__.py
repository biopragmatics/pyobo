# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from .reference import Reference  # noqa: F401
from .struct import Obo, Synonym, SynonymTypeDef, Term  # noqa: F401
from .typedef import TypeDef, from_species, get_reference_tuple, has_member, has_part, part_of, subclass  # noqa: F401
