# -*- coding: utf-8 -*-

"""Default typedefs, references, and other structures."""

from .struct import Reference, TypeDef

__all__ = [
    'from_species',
    'has_part',
    'part_of',
    'subclass',
    'has_role',
    'role_of',
    'has_mature',
    'example_of_usage',
    'alternative_term',
    'editor_note',
]

from_species = TypeDef(
    reference=Reference(prefix='ro', identifier='0002162', name='in taxon'),
)

part_of = TypeDef(
    reference=Reference(prefix='bfo', identifier='0000050', name='part of'),
    comment='Inverse of has_part',
    inverse=Reference(prefix='bfo', identifier='0000051', name='has part'),
)
has_part = TypeDef(
    reference=Reference(prefix='bfo', identifier='0000051', name='has part'),
    comment='Inverse of part_of',
    inverse=Reference(prefix='bfo', identifier='0000050', name='part of'),
)

subclass = TypeDef(
    reference=Reference(prefix='pyobo', identifier='subclass', name='subclass'),
    comment='Inverse of isA',
)

has_role = TypeDef(
    reference=Reference(prefix='ro', identifier='0000087', name='has role'),
    definition='a relation between an independent continuant (the bearer) and a role,'
               ' in which the role specifically depends on the bearer for its existence',
    domain=Reference(prefix='bfo', identifier='0000004', name='independent continuant'),
    range=Reference(prefix='bfo', identifier='0000023', name='role'),
    parents=[Reference(prefix='ro', identifier='0000053', name='bearer of')],
    inverse=Reference(prefix='ro', identifier='0000081', name='role of'),
)

role_of = TypeDef(
    reference=Reference(prefix='ro', identifier='0000081', name='role of'),
    definition='a relation between a role and an independent continuant (the bearer),'
               ' in which the role specifically depends on the bearer for its existence',
    parents=[Reference(prefix='ro', identifier='0000052', name='inheres in')],
    inverse=has_role.reference,
)

has_mature = TypeDef(
    reference=Reference(prefix='pyobo', identifier='has_mature', name='has mature miRNA'),
)

example_of_usage = Reference(prefix='iao', identifier='0000112', name='example of usage')
alternative_term = Reference(prefix='iao', identifier='0000118', name='alternative term')
editor_note = Reference(prefix='iao', identifier='0000116', name='editor note')
