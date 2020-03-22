# -*- coding: utf-8 -*-

"""Default typedefs, references, and other structures."""

from .struct import Reference, TypeDef

__all__ = [
    'from_species',
    'has_part',
    'part_of',
    'is_a',
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

is_a = TypeDef(
    reference=Reference.default(identifier='is_a', name='is a'),
    inverse=Reference.default(identifier='subclass', name='subclass'),
)

subclass = TypeDef(
    reference=Reference.default(identifier='subclass', name='subclass'),
    comment='Inverse of isA',
    inverse=Reference.default(identifier='is_a', name='is a'),
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
    reference=Reference(prefix='mirbase', identifier='has_mature', name='has mature miRNA'),
)

example_of_usage = Reference(prefix='iao', identifier='0000112', name='example of usage')
alternative_term = Reference(prefix='iao', identifier='0000118', name='alternative term')
editor_note = Reference(prefix='iao', identifier='0000116', name='editor note')

"""ChEBI"""

is_conjugate_base_of = TypeDef(
    reference=Reference(prefix='chebi', identifier='is_conjugate_base_of', name='is conjugate base of'),
)
is_conjugate_acid_of = TypeDef(
    reference=Reference(prefix='chebi', identifier='is_conjugate_acid_of', name='is conjugate acid of'),
)
is_enantiomer_of = TypeDef(
    reference=Reference(prefix='chebi', identifier='is_enantiomer_of', name='is enantiomer of'),
)
is_tautomer_of = TypeDef(
    reference=Reference(prefix='chebi', identifier='is_tautomer_of', name='is tautomer of'),
)
has_parent_hydride = TypeDef(
    reference=Reference(prefix='chebi', identifier='has_parent_hydride', name='has parent hydride'),
)
is_substituent_group_from = TypeDef(
    reference=Reference(prefix='chebi', identifier='is_substituent_group_from', name='is substituent group from'),
)
has_functional_parent = TypeDef(
    reference=Reference(prefix='chebi', identifier='has_functional_parent', name='has functional parent'),
)
