"""Tests for the OBO data structures."""

import unittest
from collections.abc import Iterable
from textwrap import dedent
from typing import cast

import bioregistry
from curies import vocabulary as v

from pyobo import Obo, Reference, default_reference
from pyobo.struct.struct import (
    Synonym,
    make_ad_hoc_ontology,
)
from pyobo.struct.struct_utils import Annotation
from pyobo.struct.typedef import (
    TypeDef,
    exact_match,
    has_contributor,
    has_inchi,
    has_role,
    part_of,
)

PREFIX = has_role.prefix
IDENTIFIER = has_role.identifier
REF = Reference(prefix=has_role.prefix, identifier=has_role.identifier)
ONTOLOGY_PREFIX = "go"


def _ontology_from_typedef(prefix: str, typedef: TypeDef) -> Obo:
    name = cast(str, bioregistry.get_name(prefix))
    return make_ad_hoc_ontology(
        _ontology=prefix,
        _name=name,
        _typedefs=[typedef],
        terms=[],
    )


class TestTypeDef(unittest.TestCase):
    """Test type definitions."""

    def assert_lines(self, text: str, lines: Iterable[str]) -> None:
        """Assert the lines are equal."""
        self.assertEqual(dedent(text).strip(), "\n".join(lines).strip())

    def assert_funowl_lines(self, text: str, typedef: TypeDef) -> None:
        """Assert functional OWL lines are equal."""
        from pyobo.struct.functional.obo_to_functional import get_typedef_axioms

        self.assert_lines(
            text,
            (x.to_funowl() for x in get_typedef_axioms(typedef)),
        )

    def assert_obo_stanza(
        self, text: str, typedef: TypeDef, *, ontology_prefix: str = ONTOLOGY_PREFIX
    ) -> None:
        """Assert the typedef text."""
        self.assert_lines(
            text,
            typedef.iterate_obo_lines(ontology_prefix),
        )

    def test_1_declaration(self) -> None:
        """Test the declaration."""
        object_property = TypeDef(reference=REF)
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            """,
            object_property,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            """,
            object_property,
        )

        annotation_property = TypeDef(
            reference=Reference(prefix=exact_match.prefix, identifier=exact_match.identifier),
            is_metadata_tag=True,
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: skos:exactMatch
            is_metadata_tag: true
            """,
            annotation_property,
        )
        self.assert_funowl_lines(
            """\
            Declaration( AnnotationProperty( skos:exactMatch ) )
            """,
            annotation_property,
        )

    def test_2_is_anonymous(self) -> None:
        """Test the ``is_anonymous`` tag."""
        typedef = TypeDef(reference=REF, is_anonymous=True)
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            is_anonymous: true
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:is_anonymous RO:0000087 "true"^^xsd:boolean )
            """,
            typedef,
        )

        typedef = TypeDef(reference=REF, is_anonymous=False)
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            is_anonymous: false
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:is_anonymous RO:0000087 "false"^^xsd:boolean )
            """,
            typedef,
        )

    def test_3_name(self) -> None:
        """Test outputting a name."""
        typedef = TypeDef(
            reference=Reference(
                prefix=has_role.prefix, identifier=has_role.identifier, name=has_role.name
            ),
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            name: has role
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( rdfs:label RO:0000087 "has role" )
            """,
            typedef,
        )

    def test_4_namespace(self) -> None:
        """Test the ``namespace`` tag."""
        typedef = TypeDef(reference=REF, namespace="NS")
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            namespace: NS
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:hasOBONamespace RO:0000087 "NS" )
            """,
            typedef,
        )

    def test_5_alt_id(self) -> None:
        """Test the ``alt_id`` tag."""
        typedef = TypeDef(
            reference=REF,
            alt_id=[
                Reference(prefix="RO", identifier="1234567"),
                Reference(prefix="RO", identifier="1234568", name="test"),
            ],
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            alt_id: RO:1234567
            alt_id: RO:1234568 ! test
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( IAO:0000118 RO:0000087 RO:1234567 )
            AnnotationAssertion( IAO:0000118 RO:0000087 RO:1234568 )
            """,
            typedef,
        )

    def test_6_description(self) -> None:
        """Test outputting a description."""
        typedef = TypeDef(reference=REF, definition=has_role.definition)
        self.assert_obo_stanza(
            f"""\
            [Typedef]
            id: RO:0000087
            def: "{has_role.definition}"
            """,
            typedef,
        )
        self.assert_funowl_lines(
            f"""\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( dcterms:description RO:0000087 "{has_role.definition}" )
            """,
            typedef,
        )

    def test_7_comment(self) -> None:
        """Test outputting a comment."""
        comment = "comment text"
        typedef = TypeDef(reference=REF, comment=comment)
        self.assert_obo_stanza(
            f"""\
            [Typedef]
            id: RO:0000087
            comment: {comment}
            """,
            typedef,
        )
        self.assert_funowl_lines(
            f"""\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( rdfs:comment RO:0000087 "{comment}" )
            """,
            typedef,
        )

    def test_8_subset(self) -> None:
        """Test the ``subset`` tag."""
        typedef = TypeDef(reference=REF, subsets=[default_reference("go", "SUBSET_1")])
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            subset: SUBSET_1
            """,
            typedef,
        )
        # note that the default ontology is "go", which is why it gets this CURIE
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:inSubset RO:0000087 obo:go#SUBSET_1 )
            """,
            typedef,
        )

    def test_9_synonym(self) -> None:
        """Test the ``synonym`` tag."""
        typedef = TypeDef(reference=REF, synonyms=[Synonym("bears role")])
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            synonym: "bears role" EXACT []
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:hasExactSynonym RO:0000087 "bears role" )
            """,
            typedef,
        )

        typedef = TypeDef(reference=REF, synonyms=[Synonym("bears role", type=v.previous_name)])
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            synonym: "bears role" EXACT OMO:0003008 []
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( Annotation( oboInOwl:hasSynonymType OMO:0003008 ) oboInOwl:hasExactSynonym RO:0000087 "bears role" )
            """,
            typedef,
        )

    def test_10_xref(self) -> None:
        """Test the ``xref`` tag."""
        typedef = TypeDef(reference=REF, xrefs=[default_reference("chebi", "has_role")])
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            xref: obo:chebi#has_role
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( oboInOwl:hasDbXref RO:0000087 obo:chebi#has_role )
            """,
            typedef,
        )

    def test_11_property_value(self) -> None:
        """Test the ``property_value`` tag."""
        typedef = TypeDef(reference=REF)
        typedef.append_property(
            Annotation(
                has_contributor.reference,
                Reference(
                    prefix=v.charlie.prefix,
                    identifier=v.charlie.identifier,
                    name=v.charlie.name,
                ),
            )
        )
        typedef.annotate_literal(has_inchi, "abc")

        self.assert_obo_stanza(
            """\
            [Typedef]
            id: RO:0000087
            property_value: dcterms:contributor orcid:0000-0003-4423-4370 ! contributor Charles Tapley Hoyt
            property_value: debio:0000020 "abc" xsd:string
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( RO:0000087 ) )
            AnnotationAssertion( RO:0000087 dcterms:contributor orcid:0000-0003-4423-4370 )
            AnnotationAssertion( RO:0000087 debio:0000020 "abc"^^xsd:string )
            """,
            typedef,
        )

    def test_12_domain(self) -> None:
        """Test the ``domain`` tag.

        Here's a real example of this tag being used in BFO:

        .. code-block::

            [Typedef]
            id: BFO:0000066
            name: occurs in
            domain: BFO:0000003 ! occurrent
            range: BFO:0000004 ! independent continuant
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of / occurs in
            inverse_of: BFO:0000067 ! contains process
            transitive_over: BFO:0000050 ! part of
        """
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            domain=Reference(prefix="BFO", identifier="0000003", name="occurrent"),
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            domain: BFO:0000003 ! occurrent
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( BFO:0000066 ) )
            ObjectPropertyDomain( BFO:0000066 BFO:0000003 )
            """,
            typedef,
        )

        typedef_annotation = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            domain=Reference(prefix="BFO", identifier="0000003", name="occurrent"),
            is_metadata_tag=True,
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            domain: BFO:0000003 ! occurrent
            is_metadata_tag: true
            """,
            typedef_annotation,
        )
        self.assert_funowl_lines(
            """\
            Declaration( AnnotationProperty( BFO:0000066 ) )
            AnnotationPropertyDomain( BFO:0000066 BFO:0000003 )
            """,
            typedef_annotation,
        )

    def test_13_range(self) -> None:
        """Test the ``range`` tag.

        Here's a real example of this tag being used in BFO:

        .. code-block::

            [Typedef]
            id: BFO:0000066
            name: occurs in
            domain: BFO:0000003 ! occurrent
            range: BFO:0000004 ! independent continuant
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of / occurs in
            inverse_of: BFO:0000067 ! contains process
            transitive_over: BFO:0000050 ! part of
        """
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            range=Reference(prefix="BFO", identifier="0000004", name="independent continuant"),
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            range: BFO:0000004 ! independent continuant
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( BFO:0000066 ) )
            ObjectPropertyRange( BFO:0000066 BFO:0000004 )
            """,
            typedef,
        )

        typedef_annotation = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            range=Reference(prefix="BFO", identifier="0000004", name="independent continuant"),
            is_metadata_tag=True,
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            range: BFO:0000004 ! independent continuant
            is_metadata_tag: true
            """,
            typedef_annotation,
        )
        self.assert_funowl_lines(
            """\
            Declaration( AnnotationProperty( BFO:0000066 ) )
            AnnotationPropertyRange( BFO:0000066 BFO:0000004 )
            """,
            typedef_annotation,
        )

    def test_14_builtin(self) -> None:
        """Test the ``builtin`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="rdfs", identifier="subClassOf"),
            builtin=True,
        )
        self.assert_obo_stanza(
            """\
           [Typedef]
           id: rdfs:subClassOf
           builtin: true
           """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( rdfs:subClassOf ) )
            AnnotationAssertion( oboInOwl:builtin rdfs:subClassOf "true"^^xsd:boolean )
            """,
            typedef,
        )

    def test_15_holds_over_chain(self) -> None:
        """Test the ``holds_over_chain`` tag.

        Here's a real example of this tag being used in BFO:

        .. code-block::

            [Typedef]
            id: BFO:0000066
            name: occurs in
            domain: BFO:0000003
            range: BFO:0000004
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of occurs in
            inverse_of: BFO:0000067 ! contains process
            transitive_over: BFO:0000050 ! part of
        """
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            holds_over_chain=[
                Reference(prefix="BFO", identifier="0000050", name="part of"),
                Reference(prefix="BFO", identifier="0000066", name="occurs in"),
            ],
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of occurs in
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( BFO:0000066 ) )
            SubObjectPropertyOf( ObjectPropertyChain( BFO:0000050 BFO:0000066 ) BFO:0000066 )
            """,
            typedef,
        )

    def test_16_is_anti_symmetric(self) -> None:
        """Test the ``anti_symmetric`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="rdfs", identifier="subClassOf"), is_anti_symmetric=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: rdfs:subClassOf
            is_anti_symmetric: true
            """,
            typedef,
        )

    def test_17_is_cyclic(self) -> None:
        """Test the ``is_cyclic`` tag."""
        typedef = TypeDef(
            reference=default_reference(prefix="chebi", identifier="is_conjugate_acid_of"),
            is_cyclic=True,
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: is_conjugate_acid_of
            is_cyclic: true
            """,
            typedef,
            ontology_prefix="chebi",
        )

    def test_18_is_reflexive(self) -> None:
        """Test the ``is_reflexive`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="rdfs", identifier="subClassOf"), is_reflexive=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: rdfs:subClassOf
            is_reflexive: true
            """,
            typedef,
        )

    def test_19_is_symmetric(self) -> None:
        """Test the ``is_symmetric`` tag."""
        typedef = TypeDef(
            reference=default_reference(prefix="ro", identifier="attached_to"), is_symmetric=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: attached_to
            is_symmetric: true
            """,
            typedef,
            ontology_prefix="ro",
        )

    def test_20_is_transitive(self) -> None:
        """Test the ``is_transitive`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="rdfs", identifier="subClassOf"), is_transitive=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: rdfs:subClassOf
            is_transitive: true
            """,
            typedef,
        )

    def test_21_is_functional(self) -> None:
        """Test the ``is_functional`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_functional=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_functional: true
            """,
            typedef,
        )

    def test_22_is_inverse_functional(self) -> None:
        """Test the ``is_inverse_functional`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_inverse_functional=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_inverse_functional: true
            """,
            typedef,
        )

    def test_23_is_a(self) -> None:
        """Test the ``is_a`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000050", name="part of"),
            parents=[Reference(prefix="RO", identifier="0002131", name="overlaps")],
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000050
            name: part of
            is_a: RO:0002131 ! overlaps
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( BFO:0000050 ) )
            AnnotationAssertion( rdfs:label BFO:0000050 "part of" )
            SubObjectPropertyOf( BFO:0000050 RO:0002131 )
            """,
            typedef,
        )

        typedef = TypeDef(
            reference=Reference(prefix="skos", identifier="exactMatch", name="exact match"),
            parents=[Reference(prefix="skos", identifier="closeMatch", name="close match")],
            is_metadata_tag=True,
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: skos:exactMatch
            name: exact match
            is_a: skos:closeMatch ! close match
            is_metadata_tag: true
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( AnnotationProperty( skos:exactMatch ) )
            AnnotationAssertion( rdfs:label skos:exactMatch "exact match" )
            SubAnnotationPropertyOf( skos:exactMatch skos:closeMatch )
            """,
            typedef,
        )

    def test_24_intersection_of(self) -> None:
        """Test the ``intersection_-f`` tag."""
        typedef = TypeDef(
            reference=Reference(
                prefix="GO", identifier="0000085", name="G2 phase of mitotic cell cycle"
            )
        )
        typedef.append_intersection_of(
            Reference(prefix="GO", identifier="0051319", name="G2 phase")
        )
        typedef.append_intersection_of(
            part_of, Reference(prefix="GO", identifier="0000278", name="mitotic cell cycle")
        )

        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000085
            name: G2 phase of mitotic cell cycle
            intersection_of: GO:0051319 ! G2 phase
            intersection_of: BFO:0000050 GO:0000278 ! part of mitotic cell cycle
            """,
            typedef,
        )
        # TODO ROBOT is broken wrt the functional OWL export of this

    def test_25_union_of(self) -> None:
        """Test the ``union_of`` tag."""

    def test_26_equivalent_to(self) -> None:
        """Test the ``equivalent_to`` tag."""

    def test_27_disjoint_from(self) -> None:
        """Test the ``disjoint_from`` tag."""

    def test_28_inverse_of(self) -> None:
        """Test the ``inverse_of`` tag.

        Here's a real example of this tag being used in BFO:

        .. code-block::

            [Typedef]
            id: BFO:0000066
            name: occurs in
            domain: BFO:0000003
            range: BFO:0000004
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of / occurs in
            inverse_of: BFO:0000067 ! contains process
            transitive_over: BFO:0000050 ! part of
        """
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            inverse=Reference(prefix="BFO", identifier="0000067", name="contains process"),
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            inverse_of: BFO:0000067 ! contains process
            """,
            typedef,
        )

    def test_29_transitive_over(self) -> None:
        """Test the ``transitive_over`` tag.

        Here's a real example of this tag being used in BFO:

        .. code-block::

            [Typedef]
            id: BFO:0000066
            name: occurs in
            domain: BFO:0000003 ! occurrent
            range: BFO:0000004 ! independent continuant
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of / occurs in
            inverse_of: BFO:0000067 ! contains process
            transitive_over: BFO:0000050 ! part of
        """
        typedef = TypeDef(
            reference=Reference(prefix="BFO", identifier="0000066"),
            transitive_over=[Reference(prefix="BFO", identifier="0000050", name="part of")],
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: BFO:0000066
            transitive_over: BFO:0000050 ! part of
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """\
            Declaration( ObjectProperty( BFO:0000066 ) )
            SubObjectPropertyOf( ObjectPropertyChain( BFO:0000066 BFO:0000050 ) BFO:0000066 )
            """,
            typedef,
        )

    def test_30_equivalent_to_chain(self) -> None:
        """Test the ``equivalent_to_chain`` tag.

        Interestingly, this property doesn't appear to be used anywhere
        on GitHub publicly except:

        - https://github.com/geneontology/go-ontology/blob/ce41588cbdc05223f9cfd029985df3cadd1e0399/src/ontology/extensions/gorel.obo#L1277-L1285
        - https://github.com/cmungall/bioperl-owl/blob/0b52048975c078d3bc50f6611235e9f8cb9b9475/ont/interval_relations.obo~#L86-L103
        """

    def test_31_disjoint_over(self) -> None:
        """Test the ``disjoint_over`` tag."""

    def test_32_relationship(self) -> None:
        """Test the ``relationship`` tag."""

    def test_33_is_obsolete(self) -> None:
        """Test the ``is_obsolete`` tag."""
        typedef = TypeDef(reference=Reference(prefix="GO", identifier="0000000"), is_obsolete=True)
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_obsolete: true
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( GO:0000000 ) )
            AnnotationAssertion( owl:deprecated GO:0000000 "true"^^xsd:boolean )
            """,
            typedef,
        )

        typedef = TypeDef(reference=Reference(prefix="GO", identifier="0000000"), is_obsolete=False)
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_obsolete: false
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( GO:0000000 ) )
            AnnotationAssertion( owl:deprecated GO:0000000 "false"^^xsd:boolean )
            """,
            typedef,
        )

    def test_34_created_by(self) -> None:
        """Test the ``created_by`` tag."""

    def test_35_creation_date(self) -> None:
        """Test the ``creation_date`` tag."""

    def test_36_replaced_by(self) -> None:
        """Test the ``replaced_by`` tag."""

    def test_37_consider(self) -> None:
        """Test the ``consider`` tag."""

    def test_40_is_metadata_tag(self) -> None:
        """Test the ``is_metadata_tag`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_metadata_tag=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_metadata_tag: true
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( AnnotationProperty( GO:0000000 ) )
            """,
            typedef,
        )

        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_metadata_tag=False
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_metadata_tag: false
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( GO:0000000 ) )
            """,
            typedef,
        )

    def test_41_is_class_level(self) -> None:
        """Test the ``is_class_level`` tag."""
        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_class_level=True
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_class_level: true
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( GO:0000000 ) )
            AnnotationAssertion( oboInOwl:is_class_level GO:0000000 "true"^^xsd:boolean )
            """,
            typedef,
        )

        typedef = TypeDef(
            reference=Reference(prefix="GO", identifier="0000000"), is_class_level=False
        )
        self.assert_obo_stanza(
            """\
            [Typedef]
            id: GO:0000000
            is_class_level: false
            """,
            typedef,
        )
        self.assert_funowl_lines(
            """
            Declaration( ObjectProperty( GO:0000000 ) )
            AnnotationAssertion( oboInOwl:is_class_level GO:0000000 "false"^^xsd:boolean )
            """,
            typedef,
        )
