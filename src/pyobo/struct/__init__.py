# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from .parser import get_terms_from_graph  # noqa: F401
from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef  # noqa: F401
from .type_defs import from_species, has_part, part_of, subclass  # noqa: F401
