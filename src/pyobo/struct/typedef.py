# -*- coding: utf-8 -*-

"""Default typedefs, references, and other structures."""

from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional, Tuple, Union

from .reference import Reference, Referenced
from ..identifier_utils import normalize_curie
from ..resources.ro import load_ro

__all__ = [
    "TypeDef",
    "RelationHint",
    "get_reference_tuple",
    "default_typedefs",
    "from_species",
    "species_specific",
    "has_part",
    "part_of",
    "is_a",
    "has_member",
    "subclass",
    "orthologous",
    "has_role",
    "role_of",
    "has_mature",
    "has_gene_product",
    "gene_product_is_a",
    "has_gene_product",
    "transcribes_to",
    "translates_to",
    "gene_product_is_a",
    "example_of_usage",
    "alternative_term",
    "editor_note",
]


@dataclass
class TypeDef(Referenced):
    """A type definition in OBO."""

    reference: Reference
    comment: Optional[str] = None
    namespace: Optional[str] = None
    definition: Optional[str] = None
    is_transitive: Optional[bool] = None
    is_symmetric: Optional[bool] = None
    domain: Optional[Reference] = None
    range: Optional[Reference] = None
    parents: List[Reference] = field(default_factory=list)
    xrefs: List[Reference] = field(default_factory=list)
    inverse: Optional[Reference] = None

    def __hash__(self) -> int:  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield "\n[Typedef]"
        yield f"id: {self.reference.curie}"
        if self.name:
            yield f"name: {self.reference.name}"

        if self.namespace:
            yield f"namespace: {self.namespace}"

        if self.comment:
            yield f"comment: {self.comment}"

        for xref in self.xrefs:
            yield f"xref: {xref}"

        if self.is_transitive is not None:
            yield f'is_transitive: {"true" if self.is_transitive else "false"}'

        if self.is_symmetric is not None:
            yield f'is_symmetric: {"true" if self.is_symmetric else "false"}'

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: Optional[str] = None) -> "TypeDef":
        """Create a typedef from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def from_curie(cls, curie: str, name: Optional[str] = None) -> "TypeDef":
        """Create a TypeDef directly from a CURIE and optional name."""
        prefix, identifier = normalize_curie(curie)
        return cls.from_triple(prefix=prefix, identifier=identifier, name=name)


RelationHint = Union[Reference, TypeDef, Tuple[str, str], str]


def get_reference_tuple(relation: RelationHint) -> Tuple[str, str]:
    """Get tuple for typedef/reference."""
    if isinstance(relation, (Reference, TypeDef)):
        return relation.prefix, relation.identifier
    elif isinstance(relation, tuple):
        return relation
    elif isinstance(relation, str):
        prefix, identifier = normalize_curie(relation)
        if prefix is None:
            raise ValueError(f"string given is not valid curie: {relation}")
        return prefix, identifier
    else:
        raise TypeError(f"Relation is invalid type: {relation}")


from_species = TypeDef(
    reference=Reference(prefix="ro", identifier="0002162", name="in taxon"),
)
species_specific = TypeDef(
    reference=Reference.default("speciesSpecific", "Species Specific"),
    definition="X speciesSpecific Y means that Y is a general phenomena, "
    "like a pathway, and X is the version that appears in a species. X should state which"
    "species with RO:0002162 (in taxon)",
)

part_of = TypeDef(
    reference=Reference(prefix="bfo", identifier="0000050", name="part of"),
    comment="Inverse of has_part",
    inverse=Reference(prefix="bfo", identifier="0000051", name="has part"),
)
has_part = TypeDef(
    reference=Reference(prefix="bfo", identifier="0000051", name="has part"),
    comment="Inverse of part_of",
    inverse=Reference(prefix="bfo", identifier="0000050", name="part of"),
)
is_a = TypeDef(
    reference=Reference.default(identifier="is_a", name="is a"),
    inverse=Reference.default(identifier="subclass", name="subclass"),
)
has_member = TypeDef(
    reference=Reference.default(identifier="has_member", name="has member"),
)
subclass = TypeDef(
    reference=Reference.default(identifier="subclass", name="subclass"),
    comment="Inverse of isA",
    inverse=Reference.default(identifier="is_a", name="is a"),
)

develops_from = TypeDef.from_triple(prefix="ro", identifier="0002202", name="develops from")
orthologous = TypeDef(
    reference=Reference(
        prefix="ro", identifier="HOM0000017", name="in orthology relationship with"
    ),
    is_symmetric=True,
)

has_role = TypeDef(
    reference=Reference(prefix="ro", identifier="0000087", name="has role"),
    definition="a relation between an independent continuant (the bearer) and a role,"
    " in which the role specifically depends on the bearer for its existence",
    domain=Reference(prefix="bfo", identifier="0000004", name="independent continuant"),
    range=Reference(prefix="bfo", identifier="0000023", name="role"),
    parents=[Reference(prefix="ro", identifier="0000053", name="bearer of")],
    inverse=Reference(prefix="ro", identifier="0000081", name="role of"),
)

role_of = TypeDef(
    reference=Reference(prefix="ro", identifier="0000081", name="role of"),
    definition="a relation between a role and an independent continuant (the bearer),"
    " in which the role specifically depends on the bearer for its existence",
    parents=[Reference(prefix="ro", identifier="0000052", name="inheres in")],
    inverse=has_role.reference,
)

has_mature = TypeDef(
    reference=Reference(prefix="mirbase", identifier="has_mature", name="has mature miRNA"),
)

has_gene_product = TypeDef(
    reference=Reference(prefix="ro", identifier="0002205", name="has gene product"),
    inverse=Reference(prefix="ro", identifier="0002204", name="gene product of"),
)
transcribes_to = TypeDef(
    reference=Reference.default(identifier="transcribes_to", name="transcribes to"),
    definition="Relation between a gene and a transcript",
)
translates_to = TypeDef(
    reference=Reference.default(identifier="translates_to", name="translates to"),
    definition="Relation between a transcript and a protein",
)
gene_product_is_a = TypeDef(
    reference=Reference.default(identifier="gene_product_is_a", name="gene product is a"),
)

example_of_usage = Reference(prefix="iao", identifier="0000112", name="example of usage")
alternative_term = Reference(prefix="iao", identifier="0000118", name="alternative term")
editor_note = Reference(prefix="iao", identifier="0000116", name="editor note")

is_immediately_transformed_from = TypeDef.from_curie(
    "sio:000658", name="is immediately transformed from"
)

"""ChEBI"""

is_conjugate_base_of = TypeDef(
    reference=Reference(
        prefix="chebi", identifier="is_conjugate_base_of", name="is conjugate base of"
    ),
)
is_conjugate_acid_of = TypeDef(
    reference=Reference(
        prefix="chebi", identifier="is_conjugate_acid_of", name="is conjugate acid of"
    ),
)
is_enantiomer_of = TypeDef(
    reference=Reference(prefix="chebi", identifier="is_enantiomer_of", name="is enantiomer of"),
)
is_tautomer_of = TypeDef(
    reference=Reference(prefix="chebi", identifier="is_tautomer_of", name="is tautomer of"),
)
has_parent_hydride = TypeDef(
    reference=Reference(prefix="chebi", identifier="has_parent_hydride", name="has parent hydride"),
)
is_substituent_group_from = TypeDef(
    reference=Reference(
        prefix="chebi", identifier="is_substituent_group_from", name="is substituent group from"
    ),
)
has_functional_parent = TypeDef(
    reference=Reference(
        prefix="chebi", identifier="has_functional_parent", name="has functional parent"
    ),
)

default_typedefs: Mapping[Tuple[str, str], TypeDef] = {
    v.pair: v for k, v in locals().items() if isinstance(v, TypeDef)
}

for pair, name in load_ro().items():
    if pair not in default_typedefs:
        default_typedefs[pair] = TypeDef.from_triple(pair[0], pair[1], name)
