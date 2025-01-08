"""Default typedefs, references, and other structures."""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated

from curies import ReferenceTuple
from typing_extensions import Self

from . import vocabulary as v
from .reference import (
    Reference,
    Referenced,
    _reference_list_tag,
    default_reference,
    reference_escape,
)
from .struct_utils import (
    AxiomsHint,
    IntersectionOfHint,
    PropertiesHint,
    RelationsHint,
    Stanza,
    _chain_tag,
    _tag_property_targets,
)
from .utils import _boolean_tag
from ..resources.ro import load_ro

if TYPE_CHECKING:
    from pyobo.struct.struct import Synonym, SynonymTypeDef

__all__ = [
    "TypeDef",
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


@dataclass
class TypeDef(Referenced, Stanza):
    """A type definition in OBO.

    See the subsection of https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.2.2.
    """

    reference: Annotated[Reference, 1]
    is_anonymous: Annotated[bool | None, 2] = None
    # 3 - name is covered by reference
    namespace: Annotated[str | None, 4] = None
    # 5 alt_id is part of proerties
    definition: Annotated[str | None, 6] = None
    comment: Annotated[str | None, 7] = None
    subsets: Annotated[list[Reference], 8] = field(default_factory=list)
    synonyms: Annotated[list[Synonym], 9] = field(default_factory=list)
    xrefs: Annotated[list[Reference], 10] = field(default_factory=list)
    _axioms: AxiomsHint = field(default_factory=lambda: defaultdict(list))
    properties: Annotated[PropertiesHint, 11] = field(default_factory=lambda: defaultdict(list))
    domain: Annotated[Reference | None, 12, "typedef-only"] = None
    range: Annotated[Reference | None, 13, "typedef-only"] = None
    builtin: Annotated[bool | None, 14] = None
    holds_over_chain: Annotated[list[list[Reference]], 15, "typedef-only"] = field(
        default_factory=list
    )
    is_anti_symmetric: Annotated[bool | None, 16, "typedef-only"] = None
    is_cyclic: Annotated[bool | None, 17, "typedef-only"] = None
    is_reflexive: Annotated[bool | None, 18, "typedef-only"] = None
    is_symmetric: Annotated[bool | None, 19, "typedef-only"] = None
    is_transitive: Annotated[bool | None, 20, "typedef-only"] = None
    is_functional: Annotated[bool | None, 21, "typedef-only"] = None
    is_inverse_functional: Annotated[bool | None, 22, "typedef-only"] = None
    parents: Annotated[list[Reference], 23] = field(default_factory=list)
    intersection_of: Annotated[IntersectionOfHint, 24] = field(default_factory=list)
    union_of: Annotated[list[Reference], 25] = field(default_factory=list)
    equivalent_to: Annotated[list[Reference], 26] = field(default_factory=list)
    disjoint_from: Annotated[list[Reference], 27] = field(default_factory=list)
    # TODO inverse should be inverse_of, cardinality any
    inverse: Annotated[Reference | None, 28, "typedef-only"] = None
    # TODO check if there are any examples of this being multiple
    transitive_over: Annotated[list[Reference], 29, "typedef-only"] = field(default_factory=list)
    equivalent_to_chain: Annotated[list[list[Reference]], 30, "typedef-only"] = field(
        default_factory=list
    )
    #: From the OBO spec:
    #:
    #:   For example: spatially_disconnected_from is disjoint_over part_of, in that two
    #:   disconnected entities have no parts in common. This can be translated to OWL as:
    #:   ``disjoint_over(R S), R(A B) ==> (S some A) disjointFrom (S some B)``
    disjoint_over: Annotated[list[Reference], 31] = field(default_factory=list)
    relationships: Annotated[RelationsHint, 32] = field(default_factory=lambda: defaultdict(list))
    is_obsolete: Annotated[bool | None, 33] = None
    created_by: Annotated[str | None, 34] = None
    creation_date: Annotated[datetime.datetime | None, 35] = None
    # TODO expand_assertion_to
    # TODO expand_expression_to
    #: Whether this relationship is a metadata tag. Properties that are marked as metadata tags are
    #: used to record object metadata. Object metadata is additional information about an object
    #: that is useful to track, but does not impact the definition of the object or how it should
    #: be treated by a reasoner. Metadata tags might be used to record special term synonyms or
    #: structured notes about a term, for example.
    is_metadata_tag: Annotated[bool | None, 40, "typedef-only"] = None
    is_class_level: Annotated[bool | None, 41] = None

    def __hash__(self) -> int:
        # have to re-define hash because of the @dataclass
        return hash((self.__class__, self.prefix, self.identifier))

    def iterate_obo_lines(
        self,
        ontology_prefix: str,
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
        typedefs: Mapping[ReferenceTuple, TypeDef] | None = None,
    ) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file.

        :param ontology_prefix:
            The prefix of the ontology into which the type definition is being written.
            This is used for compressing builtin identifiers
        :yield:
            The lines to write to an OBO file

        `S.3.5.5 <https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.3.5.5>`_
        of the OBO Flat File Specification v1.4 says tags should appear in the following order:

        1. id
        2. is_anonymous
        3. name
        4. namespace
        5. alt_id
        6. def
        7. comment
        8. subset
        9. synonym
        10. xref
        11. property_value
        12. domain
        13. range
        14. builtin
        15. holds_over_chain
        16. is_anti_symmetric
        17. is_cyclic
        18. is_reflexive
        19. is_symmetric
        20. is_transitive
        21. is_functional
        22. is_inverse_functional
        23. is_a
        24. intersection_of
        25. union_of
        26. equivalent_to
        27. disjoint_from
        28. inverse_of
        29. transitive_over
        30. equivalent_to_chain
        31. disjoint_over
        32. relationship
        33. is_obsolete
        34. created_by
        35. creation_date
        36. replaced_by
        37. consider
        38. expand_assertion_to
        39. expand_expression_to
        40. is_metadata_tag
        41. is_class_level
        """
        if synonym_typedefs is None:
            synonym_typedefs = {}
        if typedefs is None:
            typedefs = {}

        yield "\n[Typedef]"
        # 1
        yield f"id: {reference_escape(self.reference, ontology_prefix=ontology_prefix)}"
        # 2
        yield from _boolean_tag("is_anonymous", self.is_anonymous)
        # 3
        if self.name:
            yield f"name: {self.name}"
        # 4
        if self.namespace:
            yield f"namespace: {self.namespace}"
        # 5
        yield from _reference_list_tag("alt_id", self.alt_ids, ontology_prefix)
        # 6
        if self.definition:
            yield f'def: "{self.definition}"'
        # 7
        if self.comment:
            yield f"comment: {self.comment}"
        # 8
        yield from _reference_list_tag("subset", self.subsets, ontology_prefix)
        # 9
        for synonym in self.synonyms:
            yield synonym.to_obo(ontology_prefix=ontology_prefix, synonym_typedefs=synonym_typedefs)
        # 10
        yield from self._iterate_xref_obo(ontology_prefix=ontology_prefix)
        # 11
        yield from self._iterate_obo_properties(
            ontology_prefix=ontology_prefix,
            skip_predicates={
                term_replaced_by.reference,
                see_also.reference,
                alternative_term.reference,
            },
            typedefs=typedefs,
        )
        # 12
        if self.domain:
            yield f"domain: {reference_escape(self.domain, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 13
        if self.range:
            yield f"range: {reference_escape(self.range, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 14
        yield from _boolean_tag("builtin", self.builtin)
        # 15
        yield from _chain_tag("holds_over_chain", self.holds_over_chain, ontology_prefix)
        # 16
        yield from _boolean_tag("is_anti_symmetric", self.is_anti_symmetric)
        # 17
        yield from _boolean_tag("is_cyclic", self.is_cyclic)
        # 18
        yield from _boolean_tag("is_reflexive", self.is_reflexive)
        # 19
        yield from _boolean_tag("is_symmetric", self.is_symmetric)
        # 20
        yield from _boolean_tag("is_transitive", self.is_transitive)
        # 21
        yield from _boolean_tag("is_functional", self.is_functional)
        # 22
        yield from _boolean_tag("is_inverse_functional", self.is_inverse_functional)
        # 23
        yield from _reference_list_tag("is_a", self.parents, ontology_prefix)
        # 24
        yield from self._iterate_intersection_of_obo(ontology_prefix=ontology_prefix)
        # 25
        yield from _reference_list_tag("union_of", self.union_of, ontology_prefix)
        # 26
        yield from _reference_list_tag("equivalent_to", self.equivalent_to, ontology_prefix)
        # 27
        yield from _reference_list_tag("disjoint_from", self.disjoint_from, ontology_prefix)
        # 28
        if self.inverse:
            yield f"inverse_of: {reference_escape(self.inverse, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 29
        yield from _reference_list_tag("transitive_over", self.transitive_over, ontology_prefix)
        # 30
        yield from _chain_tag("equivalent_to_chain", self.equivalent_to_chain, ontology_prefix)
        # 31 disjoint_over, see https://github.com/search?q=%22disjoint_over%3A%22+path%3A*.obo&type=code
        yield from _reference_list_tag(
            "disjoint_over", self.disjoint_over, ontology_prefix=ontology_prefix
        )
        # 32
        yield from self._iterate_obo_relations(ontology_prefix=ontology_prefix, typedefs=typedefs)
        # 33
        yield from _boolean_tag("is_obsolete", self.is_obsolete)
        # 34
        if self.created_by:
            yield f"created_by: {self.created_by}"
        # 35
        if self.creation_date is not None:
            yield f"creation_date: {self.creation_date.isoformat()}"
        # 36
        yield from _tag_property_targets(
            "replaced_by", self, term_replaced_by, ontology_prefix=ontology_prefix
        )
        # 37
        yield from _tag_property_targets(
            "consider", self, see_also, ontology_prefix=ontology_prefix
        )
        # 38 TODO expand_assertion_to
        # 39 TODO expand_expression_to
        # 40
        yield from _boolean_tag("is_metadata_tag", self.is_metadata_tag)
        # 41
        yield from _boolean_tag("is_class_level", self.is_class_level)

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: str | None = None) -> TypeDef:
        """Create a typedef from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def default(cls, prefix: str, identifier: str, *, name: str | None = None) -> Self:
        """Construct a default type definition from within the OBO namespace."""
        return cls(reference=default_reference(prefix, identifier, name=name))


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
exact_match = TypeDef(
    reference=Reference(prefix="skos", identifier="exactMatch", name="exact match"),
    is_metadata_tag=True,
)
narrow_match = TypeDef(
    reference=Reference(prefix="skos", identifier="narrowMatch", name="narrow match"),
    is_metadata_tag=True,
)
broad_match = TypeDef(
    reference=Reference(prefix="skos", identifier="broadMatch", name="broad match"),
    is_metadata_tag=True,
)
close_match = TypeDef(
    reference=Reference(prefix="skos", identifier="closeMatch", name="close match"),
    is_metadata_tag=True,
)
related_match = TypeDef(
    reference=Reference(prefix="skos", identifier="relatedMatch", name="related match"),
    is_metadata_tag=True,
)
owl_same_as = TypeDef(
    reference=Reference(prefix="owl", identifier="sameAs", name="same as"),
)
equivalent_class = TypeDef(
    reference=v.equivalent_class,
)
equivalent_property = TypeDef(
    reference=Reference(prefix="owl", identifier="equivalentProperty", name="equivalent property"),
)

is_a = TypeDef(
    reference=Reference(prefix="rdfs", identifier="subClassOf", name="subclass of"),
)
see_also = TypeDef(
    reference=v.see_also,
    is_metadata_tag=True,
)
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
        [
            has_gene_product.reference,
            member_of.reference,
        ]
    ],
)

has_salt = TypeDef(
    reference=Reference(prefix="debio", identifier="0000006", name="has salt"),
)

term_replaced_by = TypeDef(
    reference=v.term_replaced_by,
    is_metadata_tag=True,
)
example_of_usage = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000112", name="example of usage"),
    is_metadata_tag=True,
)
alternative_term = TypeDef(
    reference=v.alternative_term,
    is_metadata_tag=True,
)
has_ontology_root_term = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000700", name="has ontology root term"),
    is_metadata_tag=True,
)
definition_source = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000119", name="definition source"),
    is_metadata_tag=True,
)
has_dbxref = TypeDef(
    reference=v.has_dbxref,
    is_metadata_tag=True,
)

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
    is_metadata_tag=True,
)

has_inchi = TypeDef(
    reference=Reference(prefix="debio", identifier="0000020", name="has InChI"),
    is_metadata_tag=True,
)

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
    reference=v.mapping_has_confidence,
    is_metadata_tag=True,
    range=Reference(prefix="xsd", identifier="float"),
)
has_contributor = TypeDef(
    reference=v.has_contributor,
    is_metadata_tag=True,
)

has_start_date = TypeDef(
    reference=Reference(prefix="dcat", identifier="startDate", name="has start date"),
    is_metadata_tag=True,
)
has_end_date = TypeDef(
    reference=Reference(prefix="dcat", identifier="endDate", name="has end date"),
    is_metadata_tag=True,
)

has_title = TypeDef(
    reference=Reference(prefix="dcterms", identifier="title", name="title"),
    is_metadata_tag=True,
)
has_license = TypeDef(
    reference=Reference(prefix="dcterms", identifier="license", name="license"),
    is_metadata_tag=True,
)
has_description = TypeDef(
    reference=Reference(prefix="dcterms", identifier="description", name="description"),
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

#: See https://mapping-commons.github.io/sssom/spec-model/
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
