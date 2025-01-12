"""Tests for the OBO data structures."""

import unittest
from collections.abc import Iterable
from textwrap import dedent
from typing import cast

import bioregistry

from pyobo import Obo, Reference, default_reference
from pyobo.constants import NCBITAXON_PREFIX
from pyobo.struct.functional.obo_to_functional import get_term_axioms
from pyobo.struct.reference import unspecified_matching
from pyobo.struct.struct import (
    BioregistryError,
    SynonymTypeDef,
    Term,
    TypeDef,
    make_ad_hoc_ontology,
)
from pyobo.struct.typedef import (
    exact_match,
    has_contributor,
    mapping_has_confidence,
    mapping_has_justification,
    part_of,
    see_also,
)

LYSINE_DEHYDROGENASE_ACT = Reference(
    prefix="GO", identifier="0050069", name="lysine dehydrogenase activity"
)
RO_DUMMY = TypeDef(reference=Reference(prefix="RO", identifier="1234567"))
CHARLIE = Reference(prefix="orcid", identifier="0000-0003-4423-4370")
ONTOLOGY_PREFIX = "go"


class Nope(Obo):
    """A class that will fail."""

    ontology = "nope"

    def iter_terms(self, force: bool = False):
        """Do not do anything."""


def _ontology_from_term(prefix: str, term: Term) -> Obo:
    name = cast(str, bioregistry.get_name(prefix))
    return make_ad_hoc_ontology(
        _ontology=prefix,
        _name=name,
        terms=[term],
    )


class TestStruct(unittest.TestCase):
    """Tests for the OBO data structures."""

    def test_invalid_prefix(self) -> None:
        """Test raising an error when an invalid prefix is used."""
        with self.assertRaises(BioregistryError):
            Nope()

    def test_reference_validation(self) -> None:
        """Test validation of prefix."""
        with self.assertRaises(ValueError):
            Reference(prefix="nope", identifier="also_nope")

        # For when we want to do regex checking
        # with self.assertRaises(ValueError):
        #     Reference(prefix="go", identifier="nope")
        # with self.assertRaises(ValueError):
        #     Reference(prefix="go", identifier="12345")

        r1 = Reference(prefix="go", identifier="1234567")
        self.assertEqual("go", r1.prefix)
        self.assertEqual("1234567", r1.identifier)

        r2 = Reference(prefix="GO", identifier="1234567")
        self.assertEqual("go", r2.prefix)
        self.assertEqual("1234567", r2.identifier)

        r3 = Reference(prefix="go", identifier="GO:1234567")
        self.assertEqual("go", r3.prefix)
        self.assertEqual("1234567", r3.identifier)

        r4 = Reference(prefix="GO", identifier="GO:1234567")
        self.assertEqual("go", r4.prefix)
        self.assertEqual("1234567", r4.identifier)

    def test_synonym_typedef(self) -> None:
        """Test synonym type definition serialization."""
        r1 = Reference(prefix="OMO", identifier="0003012", name="acronym")
        r2 = Reference(prefix="omo", identifier="0003012")

        s1 = SynonymTypeDef(reference=r1)
        self.assertEqual(
            'synonymtypedef: OMO:0003012 "acronym"', s1.to_obo(ontology_prefix="chebi")
        )

        s2 = SynonymTypeDef(reference=r2)
        self.assertEqual('synonymtypedef: OMO:0003012 ""', s2.to_obo(ontology_prefix="chebi"))

        s3 = SynonymTypeDef(reference=r1, specificity="EXACT")
        self.assertEqual(
            'synonymtypedef: OMO:0003012 "acronym" EXACT', s3.to_obo(ontology_prefix="chebi")
        )

        s4 = SynonymTypeDef(reference=r2, specificity="EXACT")
        self.assertEqual('synonymtypedef: OMO:0003012 "" EXACT', s4.to_obo(ontology_prefix="chebi"))


class TestTerm(unittest.TestCase):
    """Tests for terms."""

    def _assert_lines(self, text: str, lines: Iterable[str]) -> None:
        """Assert the lines are equal."""
        self.assertEqual(dedent(text).strip(), "\n".join(lines).strip())

    def assert_obo_stanza(
        self,
        term: Term,
        *,
        obo: str,
        ofn: str,
        ontology_prefix: str = ONTOLOGY_PREFIX,
        typedefs=None,
        synonym_typedefs=None,
    ) -> None:
        """Assert the typedef text."""
        self._assert_lines(
            obo,
            term.iterate_obo_lines(
                ontology_prefix=ontology_prefix,
                typedefs=typedefs or {},
                synonym_typedefs=synonym_typedefs or {},
            ),
        )
        self._assert_lines(ofn, (x.to_funowl() for x in get_term_axioms(term)))

    def assert_funowl_lines(self, text: str, term: Term) -> None:
        """Assert functional OWL lines are equal."""
        raise NotImplementedError

    def assert_boolean_tag(self, name: str, *, curie: str | None = None) -> None:
        """Assert the boolean tag parses properly."""
        if curie is None:
            curie = f"oboInOwl:{name}"
        reference = Reference(prefix="GO", identifier="0000001")
        term = Term(reference=reference, **{name: True})
        self.assert_obo_stanza(
            term,
            obo=f"""\
                [Term]
                id: GO:0000001
                {name}: true
            """,
            ofn=f"""
                Declaration(Class(GO:0000001))
                AnnotationAssertion({curie} GO:0000001 "true"^^xsd:boolean)
            """,
        )
        self.assertTrue(hasattr(term, name))
        value = getattr(term, name)
        self.assertIsNotNone(value)
        self.assertTrue(value)

        term = Term(reference=reference, **{name: False})
        self.assert_obo_stanza(
            term,
            obo=f"""\
                [Term]
                id: GO:0000001
                {name}: false
            """,
            ofn=f"""
                Declaration(Class(GO:0000001))
                AnnotationAssertion({curie} GO:0000001 "false"^^xsd:boolean)
            """,
        )
        self.assertTrue(hasattr(term, name))
        value = getattr(term, name)
        self.assertIsNotNone(value)
        self.assertFalse(value)

    def test_instance_of(self) -> None:
        """Test an instance with a class assertion."""
        term = Term(reference=default_reference("go", "example"), type="Instance")
        term.append_parent(LYSINE_DEHYDROGENASE_ACT)
        self.assert_obo_stanza(
            term,
            obo="""\
                [Instance]
                id: example
                instance_of: GO:0050069 ! lysine dehydrogenase activity
            """,
            ofn="""\
                Declaration(NamedIndividual(obo:go#example))
                ClassAssertion(GO:0050069 obo:go#example)
            """,
            # iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_1_term_minimal(self) -> None:
        """Test emitting properties."""
        term = Term(
            reference=Reference(
                prefix=LYSINE_DEHYDROGENASE_ACT.prefix,
                identifier=LYSINE_DEHYDROGENASE_ACT.identifier,
            )
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
            """,
        )

    def test_1_default_term(self) -> None:
        """Test when a term uses a default reference."""
        term = Term(reference=default_reference("gard", identifier="genetics", name="Genetics"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: genetics
                name: Genetics
            """,
            ofn="""\
                Declaration(Class(obo:gard#genetics))
                AnnotationAssertion(rdfs:label obo:gard#genetics "Genetics")
            """,
            ontology_prefix="gard",
        )

    def test_2_is_anonymous(self) -> None:
        """Test the ``is_anonymous`` tag."""
        self.assert_boolean_tag("is_anonymous")

    def test_3_term_with_name(self) -> None:
        """Test emitting properties."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
            """,
        )

    def test_4_namespace(self) -> None:
        """Test the ``namespace`` tag."""
        term = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            namespace="gomf",
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                namespace: gomf
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(oboInOwl:hasOBONamespace GO:0050069 "gomf")
            """,
        )

    def test_5_alt(self) -> None:
        """Test adding an alternate ID."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_alt(Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                alt_id: GO:1234569 ! dummy
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(IAO:0100001 GO:1234569 GO:0050069)
            """,
        )

    def test_6_definition(self):
        """Test adding a definition."""
        term = Term(LYSINE_DEHYDROGENASE_ACT, definition="Something")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                def: "Something" []
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(dcterms:description GO:0050069 "Something")
            """,
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT, definition="Something")
        term.append_definition_xref(CHARLIE)
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                def: "Something" [orcid:0000-0003-4423-4370]
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(Annotation(oboInOwl:hasDbXref orcid:0000-0003-4423-4370) dcterms:description GO:0050069 "Something")
            """,
        )

    def test_7_comment(self) -> None:
        """Test appending a comment."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_comment("I like this record")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                comment: "I like this record"
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(rdfs:comment GO:0050069 "I like this record"^^xsd:string)
            """,
        )

    def test_8_subset(self) -> None:
        """Test the ``subset`` tag."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_subset(default_reference("go", "TESTSET"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                subset: TESTSET
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(oboInOwl:inSubset GO:0050069 obo:go#TESTSET)
            """,
        )

    def test_9_append_exact_synonym(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                synonym: "L-lysine:NAD+ oxidoreductase" EXACT []
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(oboInOwl:hasExactSynonym GO:0050069 "L-lysine:NAD+ oxidoreductase")
            """,
        )

    def test_9_append_related_synonym(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            specificity="RELATED",
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                synonym: "L-lysine:NAD+ oxidoreductase" RELATED []
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(oboInOwl:hasRelatedSynonym GO:0050069 "L-lysine:NAD+ oxidoreductase")
            """,
        )

    def test_9_provenance(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase", specificity="RELATED", provenance=[CHARLIE]
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                synonym: "L-lysine:NAD+ oxidoreductase" RELATED [orcid:0000-0003-4423-4370]
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(Annotation(oboInOwl:hasDbXref orcid:0000-0003-4423-4370) oboInOwl:hasRelatedSynonym GO:0050069 "L-lysine:NAD+ oxidoreductase")
            """,
        )

    def test_9_provenance_and_type(self) -> None:
        """Test appending a synonym."""
        omo_dummy = SynonymTypeDef(reference=Reference(prefix="OMO", identifier="1234567"))
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            type=omo_dummy,
            provenance=[Reference(prefix="orcid", identifier="0000-0003-4423-4370")],
        )
        self.assert_obo_stanza(
            term,
            synonym_typedefs={omo_dummy.pair: omo_dummy},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                synonym: "L-lysine:NAD+ oxidoreductase" EXACT OMO:1234567 [orcid:0000-0003-4423-4370]
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(Annotation(oboInOwl:hasDbXref orcid:0000-0003-4423-4370) Annotation(oboInOwl:hasSynonymType OMO:1234567) oboInOwl:hasExactSynonym GO:0050069 "L-lysine:NAD+ oxidoreductase")
            """,
        )

    def test_9_append_synonym_missing_typedef(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            type=Reference(prefix="OMO", identifier="1234567"),
        )
        with self.assertLogs(level="INFO") as log:
            self.assert_obo_stanza(
                term,
                obo="""\
                    [Term]
                    id: GO:0050069
                    name: lysine dehydrogenase activity
                    synonym: "L-lysine:NAD+ oxidoreductase" EXACT OMO:1234567 []
                """,
                ofn="""
                    Declaration(Class(GO:0050069))
                    AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                    AnnotationAssertion(Annotation(oboInOwl:hasSynonymType OMO:1234567) oboInOwl:hasExactSynonym GO:0050069 "L-lysine:NAD+ oxidoreductase")
                """,
            )
        self.assertIn(
            "WARNING:pyobo.struct.struct:[go] synonym typedef not defined: OMO:1234567", log.output
        )

    def test_10_xref(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_xref(Reference(prefix="eccode", identifier="1.4.1.15"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                xref: eccode:1.4.1.15
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(oboInOwl:hasDbXref GO:0050069 eccode:1.4.1.15)
            """,
        )

        ontology = _ontology_from_term("go", term)
        mappings_df = ontology.get_mappings_df()
        self.assertEqual(
            ["subject_id", "object_id", "predicate_id", "mapping_justification"],
            list(mappings_df.columns),
        )
        self.assertEqual(
            ["GO:0050069", "eccode:1.4.1.15", "oboInOwl:hasDbXref", "semapv:UnspecifiedMatching"],
            list(mappings_df.values[0]),
        )

    def test_10_append_xref_with_axioms(self) -> None:
        """Test emitting a xref with axioms."""
        target = Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase")
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_xref(target, confidence=0.99)
        self.assert_obo_stanza(
            term,
            obo="""
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                xref: eccode:1.4.1.15 {sssom:confidence=0.99} ! lysine dehydrogenase
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(Annotation(sssom:confidence "0.99"^^xsd:float) oboInOwl:hasDbXref GO:0050069 eccode:1.4.1.15)
            """,
            typedefs={
                mapping_has_confidence.pair: mapping_has_confidence,
                mapping_has_justification.pair: mapping_has_justification,
                has_contributor.pair: has_contributor,
            },
        )

        ontology = _ontology_from_term("go", term)
        mappings_df = ontology.get_mappings_df()
        self.assertEqual(
            ["subject_id", "object_id", "predicate_id", "mapping_justification", "confidence"],
            list(mappings_df.columns),
        )
        self.assertEqual(
            [
                "GO:0050069",
                "eccode:1.4.1.15",
                "oboInOwl:hasDbXref",
                "semapv:UnspecifiedMatching",
                0.99,
            ],
            list(mappings_df.values[0]),
        )

    def test_11_builtin(self) -> None:
        """Test the builting tag."""
        self.assert_boolean_tag("builtin")

    def test_12_property_default_reference(self) -> None:
        """Test adding a replaced by."""
        r = default_reference("go", "hey")
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(r, Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_obo_stanza(
            term,
            typedefs={r.pair: r},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: hey GO:1234569
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(obo:go#hey GO:0050069 GO:1234569)
            """,
        )

    def test_12_property_literal(self) -> None:
        """Test emitting property literals."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_literal(RO_DUMMY, "value")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: RO:1234567 "value" xsd:string
            """,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(RO:1234567 GO:0050069 "value"^^xsd:string)
            """,
        )

    def test_12_property_integer(self) -> None:
        """Test emitting property literals that were annotated as a boolean."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_integer(RO_DUMMY, 1234)
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: RO:1234567 "1234" xsd:integer
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(RO:1234567 GO:0050069 "1234"^^xsd:integer)
            """,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
        )

    def test_12_property_bool(self) -> None:
        """Test emitting property literals that were annotated as a boolean."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_boolean(RO_DUMMY, True)
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: RO:1234567 "true" xsd:boolean
            """,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(RO:1234567 GO:0050069 "true"^^xsd:boolean)
            """,
        )

    def test_12_property_year(self) -> None:
        """Test emitting property literals that were annotated as a year."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_year(RO_DUMMY, "1993")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: RO:1234567 "1993" xsd:gYear
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(RO:1234567 GO:0050069 "1993"^^xsd:gYear)
            """,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
        )

    def test_12_property_object(self) -> None:
        """Test emitting property literals."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(RO_DUMMY, Reference(prefix="hgnc", identifier="123"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: RO:1234567 hgnc:123
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(RO:1234567 GO:0050069 hgnc:123)
            """,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
        )

    def test_13_parent(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_parent(Reference(prefix="GO", identifier="1234568"))
        self.assert_obo_stanza(
            term,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                is_a: GO:1234568
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                SubClassOf(GO:0050069 GO:1234568)
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
            """,
        )

    def test_14_intersection_of(self) -> None:
        """Test emitting intersection of."""
        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_intersection_of(Reference(prefix="CL", identifier="0000540", name="neuron"))
        term.append_intersection_of(
            part_of.reference,
            Reference(prefix="NCBITaxon", identifier="7955", name="zebrafish"),
        )
        self.assert_obo_stanza(
            term,
            ontology_prefix="zfa",
            obo="""\
                [Term]
                id: ZFA:0000134
                intersection_of: CL:0000540 ! neuron
                intersection_of: BFO:0000050 NCBITaxon:7955 ! part of zebrafish
            """,
            ofn="""\
                Declaration(Class(ZFA:0000134))
                EquivalentClasses(ZFA:0000134 ObjectIntersectionOf(CL:0000540 ObjectSomeValuesFrom(BFO:0000050 NCBITaxon:7955)))
            """,
        )

    def test_15_union_of(self) -> None:
        """Test emitting union of."""
        term = Term(reference=Reference(prefix="GO", identifier="1"))
        term.append_union_of(Reference(prefix="GO", identifier="2"))
        term.append_union_of(Reference(prefix="GO", identifier="3"))
        self.assert_obo_stanza(
            term,
            obo="""
                [Term]
                id: GO:1
                union_of: GO:2
                union_of: GO:3
            """,
            ofn="""
                Declaration(Class(GO:1))
                EquivalentClasses(GO:1 ObjectUnionOf(GO:2 GO:3))
            """,
        )

        term = Term(reference=Reference(prefix="GO", identifier="1"))
        term.append_union_of(Reference(prefix="GO", identifier="2"))
        term.append_union_of(Reference(prefix="GO", identifier="3"))
        term.append_union_of(Reference(prefix="GO", identifier="4"))
        self.assert_obo_stanza(
            term,
            obo="""
                [Term]
                id: GO:1
                union_of: GO:2
                union_of: GO:3
                union_of: GO:4
            """,
            ofn="""
                Declaration(Class(GO:1))
                EquivalentClasses(GO:1 ObjectUnionOf(GO:2 GO:3 GO:4))
            """,
        )

    def test_16_equivalent_classes(self) -> None:
        """Test emitting equivalent classes."""
        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_equivalent_to(Reference(prefix="GO", identifier="0"))
        self.assert_obo_stanza(
            term,
            ontology_prefix="zfa",
            obo="""\
                [Term]
                id: ZFA:0000134
                equivalent_to: GO:0
            """,
            ofn="""
                Declaration(Class(ZFA:0000134))
                EquivalentClasses(ZFA:0000134 GO:0)
            """,
        )

        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_equivalent_to(Reference(prefix="GO", identifier="0"))
        term.append_equivalent_to(Reference(prefix="GO", identifier="1"))
        self.assert_obo_stanza(
            term,
            ontology_prefix="zfa",
            obo="""\
                [Term]
                id: ZFA:0000134
                equivalent_to: GO:0
                equivalent_to: GO:1
            """,
            ofn="""
                Declaration(Class(ZFA:0000134))
                EquivalentClasses(ZFA:0000134 GO:0 GO:1)
            """,
        )

    def test_17_disjoint_from(self) -> None:
        """Test the ``disjoint_from`` tag."""
        term = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            disjoint_from=[
                Reference(prefix="GO", identifier="0000000"),
                Reference(prefix="GO", identifier="0000001"),
            ],
        )
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                disjoint_from: GO:0000000
                disjoint_from: GO:0000001
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                DisjointClasses(GO:0050069 GO:0000000 GO:0000001)
            """,
        )

    def test_18_relation(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_relationship(RO_DUMMY, Reference(prefix="eccode", identifier="1.4.1.15"))
        self.assert_obo_stanza(
            term,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                relationship: RO:1234567 eccode:1.4.1.15
            """,
            ofn="""\
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                SubClassOf(GO:0050069 ObjectSomeValuesFrom(RO:1234567 eccode:1.4.1.15))
            """,
        )

    def test_18_append_exact_match(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_exact_match(
            Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase")
        )
        self.assert_obo_stanza(
            term,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(skos:exactMatch GO:0050069 eccode:1.4.1.15)
            """,
        )

        ontology = _ontology_from_term("go", term)
        mappings_df = ontology.get_mappings_df()
        self.assertEqual(
            ["subject_id", "object_id", "predicate_id", "mapping_justification"],
            list(mappings_df.columns),
        )
        self.assertEqual(
            ["GO:0050069", "eccode:1.4.1.15", "skos:exactMatch", "semapv:UnspecifiedMatching"],
            list(mappings_df.values[0]),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_exact_match(
            Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase")
        )
        self.assert_obo_stanza(
            term,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(skos:exactMatch GO:0050069 eccode:1.4.1.15)
            """,
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(
            exact_match,
            Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase"),
        )
        self.assert_obo_stanza(
            term,
            typedefs={RO_DUMMY.pair: RO_DUMMY},
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(skos:exactMatch GO:0050069 eccode:1.4.1.15)
            """,
        )

    def test_18_set_species(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.set_species("9606", "Homo sapiens")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                relationship: RO:0002162 NCBITaxon:9606 ! in taxon Homo sapiens
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                SubClassOf(GO:0050069 ObjectSomeValuesFrom(RO:0002162 NCBITaxon:9606))
            """,
        )

        species = term.get_species()
        self.assertIsNotNone(species)
        self.assertEqual("ncbitaxon", species.prefix)
        self.assertEqual("9606", species.identifier)

    def test_18_species(self) -> None:
        """Test setting and getting species."""
        term = Term(reference=Reference(prefix="hgnc", identifier="1234"))
        term.set_species("9606", "Homo sapiens")
        species = term.get_species()
        self.assertIsNotNone(species)
        self.assertEqual(NCBITAXON_PREFIX, species.prefix)
        self.assertEqual("9606", species.identifier)

    def test_18_append_exact_match_axioms(self) -> None:
        """Test emitting a relationship with axioms."""
        target = Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase")
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_exact_match(
            target,
            mapping_justification=unspecified_matching,
            confidence=0.99,
        )
        self.assert_obo_stanza(
            term,
            typedefs={
                RO_DUMMY.pair: RO_DUMMY,
                mapping_has_confidence.pair: mapping_has_confidence,
                mapping_has_justification.pair: mapping_has_justification,
                has_contributor.pair: has_contributor,
            },
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: skos:exactMatch eccode:1.4.1.15 {sssom:confidence=0.99, \
sssom:mapping_justification=semapv:UnspecifiedMatching} ! exact match lysine dehydrogenase
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(Annotation(sssom:mapping_justification semapv:UnspecifiedMatching) Annotation(sssom:confidence "0.99"^^xsd:float) skos:exactMatch GO:0050069 eccode:1.4.1.15)
            """,
        )

        mappings = list(term.get_mappings(add_context=True))
        self.assertEqual(1, len(mappings))
        predicate, target_, context = mappings[0]
        self.assertEqual(exact_match.reference, predicate)
        self.assertEqual(target, target_)
        self.assertEqual(unspecified_matching, context.justification)
        self.assertEqual(0.99, context.confidence)
        self.assertIsNone(context.contributor)

        ontology = _ontology_from_term("go", term)
        mappings_df = ontology.get_mappings_df()
        self.assertEqual(
            ["subject_id", "object_id", "predicate_id", "mapping_justification", "confidence"],
            list(mappings_df.columns),
        )
        self.assertEqual(
            [
                "GO:0050069",
                "eccode:1.4.1.15",
                "skos:exactMatch",
                "semapv:UnspecifiedMatching",
                0.99,
            ],
            list(mappings_df.values[0]),
        )

    def test_18_see_also_single(self) -> None:
        """Test appending see also."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_see_also_uri("https://example.org/test")
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                property_value: rdfs:seeAlso "https://example.org/test" xsd:anyURI
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(rdfs:seeAlso GO:0050069 "https://example.org/test"^^xsd:anyURI)
            """,
        )

        self.assertEqual(
            "https://example.org/test",
            term.get_property(see_also),
        )

        self.assertEqual(
            ["https://example.org/test"],
            term.get_property_literals(see_also),
        )

    def test_18_see_also_double(self) -> None:
        """Test appending see also."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        with self.assertRaises(ValueError):
            term.append_see_also("something")

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_see_also(Reference(prefix="hgnc", identifier="1234", name="dummy 1"))
        term.append_see_also(Reference(prefix="hgnc", identifier="1235", name="dummy 2"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                consider: hgnc:1234 ! dummy 1
                consider: hgnc:1235 ! dummy 2
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(rdfs:seeAlso GO:0050069 hgnc:1234)
                AnnotationAssertion(rdfs:seeAlso GO:0050069 hgnc:1235)
            """,
        )

        self.assertEqual(
            [
                Reference(prefix="hgnc", identifier="1234", name="dummy 1").curie,
                Reference(prefix="hgnc", identifier="1235", name="dummy 2").curie,
            ],
            term.get_property_literals(see_also),
        )

        self.assertIsNone(term.get_relationship(exact_match))
        self.assertIsNone(term.get_species())

    def test_19_created_by(self) -> None:
        """Test the ``created_by`` tag."""

    def test_20_creation_date(self) -> None:
        """Test the ``creation_date`` tag."""

    def test_21_obsolete(self) -> None:
        """Test obsolete definition."""
        self.assert_boolean_tag("is_obsolete", curie="owl:deprecated")

    def test_22_replaced_by(self) -> None:
        """Test adding a replaced by."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_replaced_by(Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_obo_stanza(
            term,
            obo="""\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                replaced_by: GO:1234569 ! dummy
            """,
            ofn="""
                Declaration(Class(GO:0050069))
                AnnotationAssertion(rdfs:label GO:0050069 "lysine dehydrogenase activity")
                AnnotationAssertion(IAO:0100001 GO:0050069 GO:1234569)
            """,
        )