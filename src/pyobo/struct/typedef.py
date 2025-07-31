"""Default typedefs, references, and other structures."""

from __future__ import annotations

from collections.abc import Sequence

from curies import ReferenceTuple

from . import vocabulary as v
from .reference import Reference, default_reference
from .struct import TypeDef
from ..resources.ro import load_ro

__all__ = [
    "alternative_term",
    "broad_match",
    "close_match",
    "default_typedefs",
    "editor_note",
    "enables",
    "exact_match",
    "example_of_usage",
    "from_species",
    "gene_product_member_of",
    "has_contributor",
    "has_dbxref",
    "has_end_date",
    "has_gene_product",
    "has_homepage",
    "has_inchi",
    "has_mature",
    "has_member",
    "has_part",
    "has_participant",
    "has_predecessor",
    "has_role",
    "has_salt",
    "has_smiles",
    "has_start_date",
    "has_successor",
    "has_taxonomy_rank",
    "is_a",
    "located_in",
    "mapping_has_confidence",
    "mapping_has_justification",
    "match_typedefs",
    "member_of",
    "narrow_match",
    "orthologous",
    "part_of",
    "participates_in",
    "related_match",
    "role_of",
    "see_also",
    "species_specific",
    "superclass_of",
    "transcribes_to",
    "translates_to",
]

RO_PREFIX = "RO"
BFO_PREFIX = "BFO"
IAO_PREFIX = "IAO"
SIO_PREFIX = "SIO"

from_species = TypeDef(reference=v.from_species)
species_specific = TypeDef(
    reference=v.species_specific,
    definition="X speciesSpecific Y means that Y is a general phenomena, "
    "like a pathway, and X is the version that appears in a species. X should state which"
    "species with RO:0002162 (in taxon)",
)
has_left_to_right_reaction = TypeDef(v.has_left_to_right_reaction, is_metadata_tag=True)
has_right_to_left_reaction = TypeDef(v.has_right_to_left_reaction, is_metadata_tag=True)
has_bidirectional_reaction = TypeDef(
    reference=default_reference("RO", "hasBiDirectionalReaction"),
    is_metadata_tag=True,
).append_xref(Reference(prefix="debio", identifier="0000009", name="has bi-directional reaction"))
reaction_enabled_by_molecular_function = TypeDef(
    reference=default_reference("RO", "reactionEnabledByMolecularFunction")
).append_xref(
    Reference(prefix="debio", identifier="0000047", name="reaction enabled by molecular function")
)

part_of = TypeDef(reference=v.part_of, comment="Inverse of has_part", inverse=v.has_part)
has_part = TypeDef(reference=v.has_part, comment="Inverse of part_of", inverse=v.part_of)
occurs_in = TypeDef(
    reference=Reference(prefix=BFO_PREFIX, identifier="BFO:0000066", name="occurs in")
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
has_component = TypeDef(
    reference=Reference(prefix=RO_PREFIX, identifier="0002180", name="has component"),
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
exact_match = TypeDef(reference=v.exact_match, is_metadata_tag=True)
narrow_match = TypeDef(reference=v.narrow_match, is_metadata_tag=True)
broad_match = TypeDef(reference=v.broad_match, is_metadata_tag=True)
close_match = TypeDef(reference=v.close_match, is_metadata_tag=True)
related_match = TypeDef(reference=v.related_match, is_metadata_tag=True)
owl_same_as = TypeDef(
    reference=v.owl_same_as,
)
equivalent_class = TypeDef(reference=v.equivalent_class)
equivalent_property = TypeDef(reference=v.equivalent_property)

is_a = TypeDef(reference=v.is_a)
rdf_type = TypeDef(reference=v.rdf_type)
subproperty_of = TypeDef(reference=v.subproperty_of)
see_also = TypeDef(reference=v.see_also, is_metadata_tag=True)
comment = TypeDef(reference=v.comment, is_metadata_tag=True)
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
orthologous = TypeDef(reference=v.orthologous, is_symmetric=True)

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
        [
            has_gene_product.reference,
            member_of.reference,
        ]
    ],
)

has_salt = TypeDef(
    reference=Reference(prefix="debio", identifier="0000006", name="has salt"),
)

term_replaced_by = TypeDef(reference=v.term_replaced_by, is_metadata_tag=True)
example_of_usage = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000112", name="example of usage"),
    is_metadata_tag=True,
)
alternative_term = TypeDef(reference=v.alternative_term, is_metadata_tag=True)
has_ontology_root_term = TypeDef(reference=v.has_ontology_root_term, is_metadata_tag=True)
definition_source = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000119", name="definition source"),
    is_metadata_tag=True,
)
has_dbxref = TypeDef(reference=v.has_dbxref, is_metadata_tag=True)

editor_note = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000116", name="editor note"),
    is_metadata_tag=True,
)

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

# ChEBI

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

has_citation = TypeDef(
    reference=v.has_citation,
    is_metadata_tag=True,
    range=Reference(prefix="IAO", identifier="0000013", name="journal article"),
)

has_smiles = TypeDef(reference=v.has_smiles, is_metadata_tag=True).append_xref(v.debio_has_smiles)

has_inchi = TypeDef(reference=v.has_inchi, is_metadata_tag=True).append_xref(v.debio_has_inchi)

has_homepage = TypeDef(
    reference=Reference(prefix="foaf", identifier="homepage", name="homepage"), is_metadata_tag=True
)

has_category = TypeDef(
    reference=Reference(prefix="biolink", identifier="category", name="has category"),
    is_metadata_tag=True,
)

has_taxonomy_rank = TypeDef(
    reference=Reference(prefix="taxrank", identifier="1000000", name="has rank"),
    is_metadata_tag=True,
)

mapping_has_justification = TypeDef(
    reference=v.mapping_has_justification,
    is_metadata_tag=True,
    range=Reference(prefix="semapv", identifier="Matching", name="matching process"),
)
mapping_has_confidence = TypeDef(
    reference=v.mapping_has_confidence, is_metadata_tag=True, range=v.xsd_float
)
has_contributor = TypeDef(reference=v.has_contributor, is_metadata_tag=True)
has_source = TypeDef(reference=v.has_source, is_metadata_tag=True)

has_start_date = TypeDef(
    reference=Reference(prefix="dcat", identifier="startDate", name="has start date"),
    is_metadata_tag=True,
)
has_end_date = TypeDef(
    reference=Reference(prefix="dcat", identifier="endDate", name="has end date"),
    is_metadata_tag=True,
)

has_title = TypeDef(reference=v.has_title, is_metadata_tag=True)
has_license = TypeDef(reference=v.has_license, is_metadata_tag=True)
has_description = TypeDef(reference=v.has_description, is_metadata_tag=True)
obo_autogenerated_by = TypeDef(reference=v.obo_autogenerated_by, is_metadata_tag=True)
obo_has_format_version = TypeDef(reference=v.obo_has_format_version, is_metadata_tag=True)
obo_is_metadata_tag = TypeDef(reference=v.obo_is_metadata_tag, is_metadata_tag=True)
obo_has_id = TypeDef(reference=v.obo_has_id, is_metadata_tag=True)

in_subset = TypeDef(reference=v.in_subset, is_metadata_tag=True)
has_term_editor = TypeDef(reference=v.has_term_editor, is_metadata_tag=True)

default_typedefs: dict[ReferenceTuple, TypeDef] = {
    v.pair: v for v in locals().values() if isinstance(v, TypeDef)
}

for reference, name in load_ro().items():
    if reference not in default_typedefs:
        default_typedefs[reference] = TypeDef.from_triple(
            reference.prefix, reference.identifier, name
        )

#: SSSOM-compliant match type definitions
#: .. seealso:: https://mapping-commons.github.io/sssom/spec-model/
match_typedefs: Sequence[TypeDef] = (
    broad_match,
    close_match,
    exact_match,
    narrow_match,
    related_match,
    owl_same_as,  # for instances
    equivalent_class,  # for classes
    equivalent_property,  # for properties
    has_dbxref,
    see_also,
)

# Extension past the SSSOM spec
extended_match_typedefs = (
    *match_typedefs,
    alternative_term,
    term_replaced_by,
)
