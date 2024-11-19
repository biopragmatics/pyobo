"""Default typedefs, references, and other structures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from curies import ReferenceTuple

from .reference import Reference, Referenced
from ..resources.ro import load_ro

__all__ = [
    "TypeDef",
    "alternative_term",
    "default_typedefs",
    "editor_note",
    "enables",
    "exact_match",
    "example_of_usage",
    "from_species",
    "gene_product_member_of",
    "has_dbxref",
    "has_gene_product",
    "has_homepage",
    # Properties
    "has_inchi",
    "has_mature",
    "has_member",
    "has_part",
    "has_participant",
    "has_predecessor",
    "has_role",
    "has_salt",
    "has_smiles",
    "has_successor",
    "is_a",
    "located_in",
    "member_of",
    "orthologous",
    "part_of",
    "participates_in",
    "role_of",
    "see_also",
    "species_specific",
    "superclass_of",
    "transcribes_to",
    "translates_to",
]


def _bool_to_obo(v: bool) -> str:
    return "true" if v else "false"


@dataclass
class TypeDef(Referenced):
    """A type definition in OBO.

    See the subsection of https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.2.2.
    """

    reference: Reference
    comment: str | None = None
    namespace: str | None = None
    definition: str | None = None
    is_transitive: bool | None = None
    is_symmetric: bool | None = None
    domain: Reference | None = None
    range: Reference | None = None
    parents: list[Reference] = field(default_factory=list)
    xrefs: list[Reference] = field(default_factory=list)
    inverse: Reference | None = None
    created_by: str | None = None
    holds_over_chain: list[Reference] | None = None
    #: Whether this relationship is a metadata tag. Properties that are marked as metadata tags are
    #: used to record object metadata. Object metadata is additional information about an object
    #: that is useful to track, but does not impact the definition of the object or how it should
    #: be treated by a reasoner. Metadata tags might be used to record special term synonyms or
    #: structured notes about a term, for example.
    is_metadata_tag: bool | None = None

    def __hash__(self) -> int:
        return hash((self.__class__, self.prefix, self.identifier))

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield "\n[Typedef]"
        yield f"id: {self.reference.preferred_curie}"
        if self.name:
            yield f"name: {self.reference.name}"
        if self.definition:
            yield f'def: "{self.definition}"'

        if self.is_metadata_tag is not None:
            yield f"is_metadata_tag: {_bool_to_obo(self.is_metadata_tag)}"

        if self.namespace:
            yield f"namespace: {self.namespace}"

        if self.created_by:
            yield f"created_by: {self.created_by}"

        if self.comment:
            yield f"comment: {self.comment}"

        for xref in self.xrefs:
            yield f"xref: {xref.preferred_curie}"

        if self.is_transitive is not None:
            yield f'is_transitive: {"true" if self.is_transitive else "false"}'

        if self.is_symmetric is not None:
            yield f'is_symmetric: {"true" if self.is_symmetric else "false"}'
        if self.holds_over_chain:
            _chain = " ".join(link.preferred_curie for link in self.holds_over_chain)
            _names = " / ".join(link.name or "_" for link in self.holds_over_chain)
            yield f"holds_over_chain: {_chain} ! {_names}"
        if self.inverse:
            yield f"inverse_of: {self.inverse}"
        if self.domain:
            yield f"domain: {self.domain}"
        if self.range:
            yield f"range: {self.range}"

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: str | None = None) -> TypeDef:
        """Create a typedef from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def from_curie(cls, curie: str, name: str | None = None) -> TypeDef:
        """Create a TypeDef directly from a CURIE and optional name."""
        reference = Reference.from_curie(curie, name=name, strict=True)
        if reference is None:
            raise RuntimeError
        return cls(reference=reference)


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
has_left_to_right_reaction = TypeDef(
    Reference(prefix="debio", identifier="0000007", name="has left-to-right reaction"),
    is_metadata_tag=True,
)
has_right_to_left_reaction = TypeDef(
    Reference(prefix="debio", identifier="0000008", name="has right-to-left reaction"),
    is_metadata_tag=True,
)
has_bidirectional_reaction = TypeDef(
    Reference(prefix="debio", identifier="0000009", name="has bi-directional reaction"),
    is_metadata_tag=True,
)
reaction_enabled_by_molecular_function = TypeDef(
    Reference(prefix="debio", identifier="0000047", name="reaction enabled by molecular function")
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
derives_from = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0001000", name="derives from"),
)
molecularly_interacts_with = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002436", name="molecularly interacts with"),
)
located_in = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0001025", name="located in"),
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

term_replaced_by = TypeDef.from_triple(
    prefix=IAO_PREFIX, identifier="0100001", name="term replaced by"
)
example_of_usage = TypeDef.from_triple(
    prefix=IAO_PREFIX, identifier="0000112", name="example of usage"
)
alternative_term = TypeDef.from_triple(
    prefix=IAO_PREFIX, identifier="0000118", name="alternative term"
)
has_ontology_root_term = TypeDef.from_triple(
    prefix=IAO_PREFIX, identifier="0000700", name="has ontology root term"
)
definition_source = TypeDef.from_triple(
    prefix=IAO_PREFIX, identifier="0000119", name="definition source"
)
has_dbxref = TypeDef.from_curie("oboInOwl:hasDbXref", name="has database cross-reference")

editor_note = TypeDef.from_triple(prefix=IAO_PREFIX, identifier="0000116", name="editor note")

is_immediately_transformed_from = TypeDef.from_triple(
    prefix=SIO_PREFIX, identifier="000658", name="is immediately transformed from"
)

_enables_reference = Reference(prefix=RO_PREFIX, identifier="0002327", name="enables")
_enabled_by_reference = Reference(prefix=RO_PREFIX, identifier="0002333", name="enabled by")
enables = TypeDef(reference=_enables_reference, inverse=_enabled_by_reference)
enabled_by = TypeDef(reference=_enabled_by_reference, inverse=_enables_reference)

has_input = TypeDef.from_triple(prefix=RO_PREFIX, identifier="0002233", name="has input")
has_output = TypeDef.from_triple(prefix=RO_PREFIX, identifier="0002234", name="has output")

has_successor = TypeDef.from_triple(prefix="BFO", identifier="0000063", name="has successor")
has_predecessor = TypeDef.from_triple(prefix="BFO", identifier="0000062", name="has predecessor")

"""ChEBI"""

is_conjugate_base_of = TypeDef(
    reference=Reference(prefix="ro", identifier="0018033", name="is conjugate base of"),
)
is_conjugate_acid_of = TypeDef(
    reference=Reference(prefix="ro", identifier="0018034", name="is conjugate acid of"),
)
is_enantiomer_of = TypeDef(
    reference=Reference(prefix="ro", identifier="0018039", name="is enantiomer of"),
)
is_tautomer_of = TypeDef(
    reference=Reference(prefix="ro", identifier="0018036", name="is tautomer of"),
)
has_parent_hydride = TypeDef(
    reference=Reference(prefix="ro", identifier="0018040", name="has parent hydride"),
)
is_substituent_group_from = TypeDef(
    reference=Reference(prefix="ro", identifier="0018037", name="is substituent group from"),
)
has_functional_parent = TypeDef(
    reference=Reference(prefix="ro", identifier="0018038", name="has functional parent"),
)

has_smiles = TypeDef(
    reference=Reference(prefix="debio", identifier="0000022", name="has SMILES"),
)

has_inchi = TypeDef(
    reference=Reference(prefix="debio", identifier="0000020", name="has InChI"),
)

has_homepage = TypeDef(
    reference=Reference(prefix="foaf", identifier="homepage", name="homepage"), is_metadata_tag=True
)

has_category = TypeDef(
    reference=Reference(prefix="biolink", identifier="category", name="has category"),
    is_metadata_tag=True,
)

default_typedefs: dict[ReferenceTuple, TypeDef] = {
    v.pair: v for v in locals().values() if isinstance(v, TypeDef)
}

for reference, name in load_ro().items():
    if reference not in default_typedefs:
        default_typedefs[reference] = TypeDef.from_triple(
            reference.prefix, reference.identifier, name
        )
