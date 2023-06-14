# -*- coding: utf-8 -*-

"""Default typedefs, references, and other structures."""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union

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
    "see_also",
    "has_member",
    "member_of",
    "superclass_of",
    "orthologous",
    "has_role",
    "role_of",
    "has_mature",
    "has_gene_product",
    "gene_product_member_of",
    "has_gene_product",
    "transcribes_to",
    "translates_to",
    "gene_product_member_of",
    "example_of_usage",
    "alternative_term",
    "editor_note",
    "has_salt",
    "enables",
    "participates_in",
    "has_participant",
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
    created_by: Optional[str] = None
    holds_over_chain: Optional[List[Reference]] = None
    #: Whether this relationship is a metadata tag. Properties that are marked as metadata tags are
    #: used to record object metadata. Object metadata is additional information about an object
    #: that is useful to track, but does not impact the definition of the object or how it should
    #: be treated by a reasoner. Metadata tags might be used to record special term synonyms or
    #: structured notes about a term, for example.
    is_metadata_tag: Optional[bool] = None

    def __hash__(self) -> int:  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield "\n[Typedef]"
        yield f"id: {self.reference.curie}"
        if self.name:
            yield f"name: {self.reference.name}"
        if self.definition:
            yield f'def: "{self.definition}"'

        if self.is_metadata_tag is not None:
            yield f'is_metadata_tag: {"true" if self.is_metadata_tag else "false"}'

        if self.namespace:
            yield f"namespace: {self.namespace}"

        if self.created_by:
            yield f"created_by: {self.created_by}"

        if self.comment:
            yield f"comment: {self.comment}"

        for xref in self.xrefs:
            yield f"xref: {xref}"

        if self.is_transitive is not None:
            yield f'is_transitive: {"true" if self.is_transitive else "false"}'

        if self.is_symmetric is not None:
            yield f'is_symmetric: {"true" if self.is_symmetric else "false"}'
        if self.holds_over_chain:
            _chain = " ".join(link.curie for link in self.holds_over_chain)
            _names = " / ".join(link.name or "_" for link in self.holds_over_chain)
            yield f"holds_over_chain: {_chain} ! {_names}"

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: Optional[str] = None) -> "TypeDef":
        """Create a typedef from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def from_curie(cls, curie: str, name: Optional[str] = None) -> "TypeDef":
        """Create a TypeDef directly from a CURIE and optional name."""
        prefix, identifier = normalize_curie(curie)
        if prefix is None or identifier is None:
            raise ValueError
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
        if prefix is None or identifier is None:
            raise ValueError(f"string given is not valid curie: {relation}")
        return prefix, identifier
    else:
        raise TypeError(f"Relation is invalid type: {relation}")


RO_PREFIX = "RO"
BFO_PREFIX = "BFO"
IAO_PREFIX = "IAO"
SIO_PREFIX = "SIO"

from_species = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002162", name="in taxon"),
)
species_specific = TypeDef(
    reference=Reference(prefix="debio", identifier="0000007", name="species specific"),
    definition="X speciesSpecific Y means that Y is a general phenomena, "
    "like a pathway, and X is the version that appears in a species. X should state which"
    "species with RO:0002162 (in taxon)",
)

part_of = TypeDef(
    reference=Reference(prefix=BFO_PREFIX, identifier="0000050", name="part of"),
    comment="Inverse of has_part",
    inverse=Reference(prefix=BFO_PREFIX, identifier="0000051", name="has part"),
)
has_part = TypeDef(
    reference=Reference(prefix=BFO_PREFIX, identifier="0000051", name="has part"),
    comment="Inverse of part_of",
    inverse=Reference(prefix=BFO_PREFIX, identifier="0000050", name="part of"),
)
participates_in = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0000056", name="participates in"),
    comment="Inverse of has participant",
    inverse=Reference(prefix=RO_PREFIX, identifier="0000057", name="has participant"),
)
has_participant = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0000057", name="has participant"),
    comment="Inverse of has participant",
    inverse=Reference(prefix=RO_PREFIX, identifier="0000056", name="participates in"),
)
exact_match = TypeDef(
    reference=Reference(prefix="skos", identifier="exactMatch", name="exact match"),
)
is_a = TypeDef(
    reference=Reference(prefix="rdfs", identifier="subClassOf", name="subclass of"),
)
see_also = TypeDef(
    reference=Reference(prefix="rdfs", identifier="seeAlso", name="see also"),
)
comment = TypeDef(reference=Reference(prefix="rdfs", identifier="comment", name="comment"))
has_member = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002351", name="has member"),
)
member_of = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002350", name="member of"),
    inverse=has_member.reference,
)
superclass_of = TypeDef(
    reference=Reference(prefix="sssom", identifier="superClassOf", name="super class of"),
    comment="Inverse of subClassOf",
    inverse=is_a.reference,
)

develops_from = TypeDef.from_triple(prefix=RO_PREFIX, identifier="0002202", name="develops from")
orthologous = TypeDef(
    reference=Reference(
        prefix=RO_PREFIX, identifier="HOM0000017", name="in orthology relationship with"
    ),
    is_symmetric=True,
)

has_role = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0000087", name="has role"),
    definition="a relation between an independent continuant (the bearer) and a role,"
    " in which the role specifically depends on the bearer for its existence",
    domain=Reference(prefix=BFO_PREFIX, identifier="0000004", name="independent continuant"),
    range=Reference(prefix=BFO_PREFIX, identifier="0000023", name="role"),
    parents=[Reference(prefix=RO_PREFIX, identifier="0000053", name="bearer of")],
    inverse=Reference(prefix=RO_PREFIX, identifier="0000081", name="role of"),
)

role_of = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0000081", name="role of"),
    definition="a relation between a role and an independent continuant (the bearer),"
    " in which the role specifically depends on the bearer for its existence",
    parents=[Reference(prefix=RO_PREFIX, identifier="0000052", name="inheres in")],
    inverse=has_role.reference,
)

has_mature = TypeDef(
    reference=Reference(prefix="debio", identifier="0000002", name="has mature miRNA"),
)

transcribes_to = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002511", name="transcribed to"),
)
translates_to = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002513", name="ribosomally translates to"),
)
gene_product_of = TypeDef.from_triple(
    prefix=RO_PREFIX, identifier="0002204", name="gene product of"
)
has_gene_product = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002205", name="has gene product"),
    inverse=gene_product_of.reference,
)  # holds over chain (transcribes_to, translates_to)
gene_product_member_of = TypeDef(
    reference=Reference(prefix="debio", identifier="0000001", name="gene product is a member of"),
    holds_over_chain=[
        has_gene_product.reference,
        member_of.reference,
    ],
)

has_salt = TypeDef(
    reference=Reference(prefix="debio", identifier="0000006", name="has salt"),
)

example_of_usage = Reference(prefix=IAO_PREFIX, identifier="0000112", name="example of usage")
alternative_term = Reference(prefix=IAO_PREFIX, identifier="0000118", name="alternative term")
editor_note = Reference(prefix=IAO_PREFIX, identifier="0000116", name="editor note")

is_immediately_transformed_from = TypeDef.from_triple(
    prefix=SIO_PREFIX, identifier="000658", name="is immediately transformed from"
)
enables = TypeDef.from_triple(prefix="RO", identifier="0002327", name="enables")

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

default_typedefs: Dict[Tuple[str, str], TypeDef] = {
    v.pair: v for k, v in locals().items() if isinstance(v, TypeDef)
}

for pair, name in load_ro().items():
    if pair not in default_typedefs:
        default_typedefs[pair] = TypeDef.from_triple(pair[0], pair[1], name)
