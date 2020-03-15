# -*- coding: utf-8 -*-

"""Default typedefs."""

from .struct import TypeDef

__all__ = [
    'from_species',
    'has_part',
    'part_of',
    'subclass',
]

from_species = TypeDef(
    id='from_species',
    name='from species',
)
has_part = TypeDef(
    id='has_part',
    name='has part',
    comment='Inverse of part_of',
)
part_of = TypeDef(
    id='part_of',
    name='part of',
    comment='Inverse of has_part',
)
subclass = TypeDef(
    id='subclass',
    name='subclass',
    comment='Inverse of isA',
)
