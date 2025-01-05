"""Default typedefs, references, and other structures."""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated

from curies import ReferenceTuple
from typing_extensions import Self

from .reference import (
    OBOLiteral,
    Reference,
    Referenced,
    default_reference,
    iterate_obo_relations,
    reference_escape,
)
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


def _bool_to_obo(v: bool) -> str:
    return "true" if v else "false"


@dataclass
class TypeDef(Referenced):
    """A type definition in OBO.

    See the subsection of https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.2.2.
    """

    reference: Annotated[Reference, 1]
    is_anonymous: Annotated[bool | None, 2] = None
    # 3 - name is covered by reference
    namespace: Annotated[str | None, 4] = None
    alt_id: Annotated[list[Reference], 5] = field(default_factory=list)
    definition: Annotated[str | None, 6] = None
    comment: Annotated[str | None, 7] = None
    subsets: Annotated[list[Reference], 8] = field(default_factory=list)
    synonyms: Annotated[list[Synonym], 9] = field(default_factory=list)
    xrefs: Annotated[list[Reference], 10] = field(default_factory=list)
    annotations: dict[
        tuple[Reference, Reference | OBOLiteral], list[tuple[Reference, Reference | OBOLiteral]]
    ] = field(default_factory=lambda: defaultdict(list))
    properties: Annotated[dict[Reference, list[Reference | OBOLiteral]], 11] = field(
        default_factory=lambda: defaultdict(list)
    )
    domain: Annotated[Reference | None, 12, "typedef-only"] = None
    range: Annotated[Reference | None, 13, "typedef-only"] = None
    builtin: Annotated[bool | None, 14] = None
    holds_over_chain: Annotated[list[Reference] | None, 15, "typedef-only"] = None
    is_anti_symmetric: Annotated[bool | None, 16, "typedef-only"] = None
    is_cyclic: Annotated[bool | None, 17, "typedef-only"] = None
    is_reflexive: Annotated[bool | None, 18, "typedef-only"] = None
    is_symmetric: Annotated[bool | None, 19, "typedef-only"] = None
    is_transitive: Annotated[bool | None, 20, "typedef-only"] = None
    is_functional: Annotated[bool | None, 21, "typedef-only"] = None
    is_inverse_functional: Annotated[bool | None, 22, "typedef-only"] = None
    parents: Annotated[list[Reference], 23] = field(default_factory=list)
    intersection_of: Annotated[list[Reference | tuple[Reference, Reference]], 24] = field(
        default_factory=list
    )
    union_of: Annotated[list[Reference], 25] = field(default_factory=list)
    equivalent_to: Annotated[list[Reference], 26] = field(default_factory=list)
    disjoint_from: Annotated[list[Reference], 27] = field(default_factory=list)
    # TODO inverse should be inverse_of, cardinality any
    inverse: Annotated[Reference | None, 28, "typedef-only"] = None
    # TODO check if there are any examples of this being multiple
    transitive_over: Annotated[list[Reference], 29, "typedef-only"] = field(default_factory=list)
    equivalent_to_chain: Annotated[list[Reference], 30, "typedef-only"] = field(
        default_factory=list
    )
    #: From the OBO spec:
    #:
    #:   For example: spatially_disconnected_from is disjoint_over part_of, in that two
    #:   disconnected entities have no parts in common. This can be translated to OWL as:
    #:   ``disjoint_over(R S), R(A B) ==> (S some A) disjointFrom (S some B)``
    disjoint_over: Annotated[Reference | None, 31] = None
    relationships: Annotated[dict[Reference, list[Reference]], 32] = field(
        default_factory=lambda: defaultdict(list)
    )
    is_obsolete: Annotated[bool | None, 33] = None
    created_by: Annotated[str | None, 34] = None
    creation_date: Annotated[datetime.datetime | None, 35] = None
    replaced_by: Annotated[list[Reference], 36] = field(default_factory=list)
    consider: Annotated[list[Reference], 37] = field(default_factory=list)
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

    def iterate_funowl_lines(self) -> Iterable[str]:
        """Iterate over lines to write in an OFN file."""
        from pyobo.struct.functional.obo_to_functional import get_typedef_axioms

        for axiom in get_typedef_axioms(self):
            yield axiom.to_funowl()

    def iterate_obo_lines(
        self,
        ontology_prefix: str,
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
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
        yield "\n[Typedef]"
        # 1
        yield f"id: {reference_escape(self.reference, ontology_prefix=ontology_prefix)}"
        # 2
        yield from self._boolean_tag("is_anonymous", self.is_anonymous)
        # 3
        if self.name:
            yield f"name: {self.name}"
        # 4
        if self.namespace:
            yield f"namespace: {self.namespace}"
        # 5
        yield from self._reference_list_tag("alt_id", self.alt_id, ontology_prefix)
        # 6
        if self.definition:
            yield f'def: "{self.definition}"'
        # 7
        if self.comment:
            yield f"comment: {self.comment}"
        # 8
        for subset in self.subsets:
            yield f"subset: {reference_escape(subset, ontology_prefix=ontology_prefix)}"
        # 9
        for synonym in self.synonyms:
            yield synonym.to_obo(
                ontology_prefix=ontology_prefix, synonym_typedefs=synonym_typedefs or {}
            )
        # 10
        yield from self._reference_list_tag("xref", self.xrefs, ontology_prefix)
        # 11
        for line in iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.properties,  # type:ignore
            self.annotations,
            ontology_prefix=ontology_prefix,
        ):
            yield f"property_value: {line}"
        # 12
        if self.domain:
            yield f"domain: {reference_escape(self.domain, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 13
        if self.range:
            yield f"range: {reference_escape(self.range, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 14
        yield from self._boolean_tag("builtin", self.builtin)
        # 15
        yield from self._chain_tag("holds_over_chain", self.holds_over_chain, ontology_prefix)
        # 16
        yield from self._boolean_tag("is_anti_symmetric", self.is_anti_symmetric)
        # 17
        yield from self._boolean_tag("is_cyclic", self.is_cyclic)
        # 18
        yield from self._boolean_tag("is_reflexive", self.is_reflexive)
        # 19
        yield from self._boolean_tag("is_symmetric", self.is_symmetric)
        # 20
        yield from self._boolean_tag("is_transitive", self.is_transitive)
        # 21
        yield from self._boolean_tag("is_functional", self.is_functional)
        # 22
        yield from self._boolean_tag("is_inverse_functional", self.is_inverse_functional)
        # 23
        yield from self._reference_list_tag("is_a", self.parents, ontology_prefix)
        # 24
        for p in self.intersection_of:
            if isinstance(p, Reference):
                yv = reference_escape(p, ontology_prefix=ontology_prefix, add_name_comment=True)
            else:  # this is a 2-tuple of references
                yv = " ".join(reference_escape(x, ontology_prefix=ontology_prefix) for x in p)
                if all(x.name for x in p):
                    yv += " ! " + " ".join(x.name for x in p)  # type:ignore
            yield f"intersection_of: {yv}"
        # 25
        yield from self._reference_list_tag("union_of", self.union_of, ontology_prefix)
        # 26
        yield from self._reference_list_tag("equivalent_to", self.equivalent_to, ontology_prefix)
        # 27
        yield from self._reference_list_tag("disjoint_from", self.disjoint_from, ontology_prefix)
        # 28
        if self.inverse:
            yield f"inverse_of: {reference_escape(self.inverse, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 29
        yield from self._reference_list_tag(
            "transitive_over", self.transitive_over, ontology_prefix
        )
        # 30
        yield from self._chain_tag("equivalent_to_chain", self.equivalent_to_chain, ontology_prefix)
        # 31 TODO disjoint_over, see https://github.com/search?q=%22disjoint_over%3A%22+path%3A*.obo&type=code
        # 32
        for line in iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.relationships,  # type:ignore
            self.annotations,
            ontology_prefix=ontology_prefix,
        ):
            yield f"relationship: {line}"
        # 33
        yield from self._boolean_tag("is_obsolete", self.is_obsolete)
        # 34
        if self.created_by:
            yield f"created_by: {self.created_by}"
        # 35
        if self.creation_date is not None:
            yield f"creation_date: {self.creation_date.isoformat()}"
        # 36
        yield from self._reference_list_tag("replaced_by", self.replaced_by, ontology_prefix)
        # 37
        yield from self._reference_list_tag(
            "consider", self.consider, ontology_prefix=ontology_prefix
        )
        # 38 TODO expand_assertion_to
        # 39 TODO expand_expression_to
        # 40
        yield from self._boolean_tag("is_metadata_tag", self.is_metadata_tag)
        # 41
        yield from self._boolean_tag("is_class_level", self.is_class_level)

    @staticmethod
    def _chain_tag(tag: str, chain: list[Reference] | None, ontology_prefix: str) -> Iterable[str]:
        if chain:
            yv = f"{tag}: "
            yv += " ".join(
                reference_escape(reference, ontology_prefix=ontology_prefix) for reference in chain
            )
            if any(reference.name for reference in chain):
                _names = " / ".join(link.name or "_" for link in chain)
                yv += f" ! {_names}"
            yield yv

    @staticmethod
    def _boolean_tag(tag: str, bv: bool | None) -> Iterable[str]:
        if bv is not None:
            yield f"{tag}: {_bool_to_obo(bv)}"

    @staticmethod
    def _reference_list_tag(
        tag: str, references: list[Reference], ontology_prefix: str
    ) -> Iterable[str]:
        for reference in references:
            yield f"{tag}: {reference_escape(reference, ontology_prefix=ontology_prefix, add_name_comment=True)}"

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
    reference=Reference(prefix="owl", identifier="equivalentClass", name="equivalent class"),
)
equivalent_property = TypeDef(
    reference=Reference(prefix="owl", identifier="equivalentProperty", name="equivalent property"),
)

is_a = TypeDef(
    reference=Reference(prefix="rdfs", identifier="subClassOf", name="subclass of"),
)
see_also = TypeDef(
    reference=Reference(prefix="rdfs", identifier="seeAlso", name="see also"),
    is_metadata_tag=True,
)
comment = TypeDef(
    reference=Reference(prefix="rdfs", identifier="comment", name="comment"), is_metadata_tag=True
)
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

term_replaced_by = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0100001", name="term replaced by"),
    is_metadata_tag=True,
)
example_of_usage = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000112", name="example of usage"),
    is_metadata_tag=True,
)
alternative_term = TypeDef(
    reference=Reference(prefix=IAO_PREFIX, identifier="0000118", name="alternative term"),
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
    reference=Reference(
        prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
    ),
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
    reference=Reference(
        prefix="sssom", identifier="mapping_justification", name="mapping justification"
    ),
    is_metadata_tag=True,
    range=Reference(prefix="semapv", identifier="Matching", name="matching process"),
)
mapping_has_confidence = TypeDef(
    reference=Reference(prefix="sssom", identifier="confidence", name="has confidence"),
    is_metadata_tag=True,
    range=Reference(prefix="xsd", identifier="float"),
)
has_contributor = TypeDef(
    reference=Reference(prefix="dcterms", identifier="contributor", name="contributor"),
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
    owl_same_as,
    equivalent_class,
    equivalent_property,
    has_dbxref,
    see_also,
)
