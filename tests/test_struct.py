"""Tests for the OBO data structures."""

import unittest
from collections.abc import Iterable
from textwrap import dedent
from typing import cast

import bioregistry

from pyobo import Obo, Reference, default_reference
from pyobo.constants import NCBITAXON_PREFIX
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

    def assert_lines(self, text: str, lines: Iterable[str]) -> None:
        """Assert the lines are equal."""
        self.assertEqual(dedent(text).strip(), "\n".join(lines).strip())

    def test_1_term_minimal(self) -> None:
        """Test emitting properties."""
        term = Term(
            reference=Reference(
                prefix=LYSINE_DEHYDROGENASE_ACT.prefix,
                identifier=LYSINE_DEHYDROGENASE_ACT.identifier,
            )
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_1_default_term(self) -> None:
        """Test when a term uses a default reference."""
        term = Term(reference=default_reference("gard", identifier="genetics", name="Genetics"))
        self.assert_lines(
            """\
            [Term]
            id: genetics
            name: Genetics
            """,
            term.iterate_obo_lines(ontology_prefix="gard", typedefs={}),
        )

    def test_2_is_anonymous(self) -> None:
        """Test the ``is_anonymous`` tag."""
        term = Term(
            reference=Reference(
                prefix=LYSINE_DEHYDROGENASE_ACT.prefix,
                identifier=LYSINE_DEHYDROGENASE_ACT.identifier,
            ),
            is_anonymous=True,
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            is_anonymous: true
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        term2 = Term(
            reference=Reference(
                prefix=LYSINE_DEHYDROGENASE_ACT.prefix,
                identifier=LYSINE_DEHYDROGENASE_ACT.identifier,
            ),
            is_anonymous=False,
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            is_anonymous: false
            """,
            term2.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_3_term_with_name(self) -> None:
        """Test emitting properties."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_4_namespace(self) -> None:
        """Test the ``namespace`` tag."""
        term = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            namespace="gomf",
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            namespace: gomf
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_5_alt(self) -> None:
        """Test adding an alternate ID."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_alt(Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            alt_id: GO:1234569 ! dummy
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_6_provenance_no_definition(self) -> None:
        """Test when there's provenance but not definition."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_provenance(CHARLIE)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            def: "" [orcid:0000-0003-4423-4370]
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_6_definition(self):
        """Test adding a definition."""
        term = Term(LYSINE_DEHYDROGENASE_ACT, definition="Something")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            def: "Something" []
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT, definition="Something")
        term.append_provenance(CHARLIE)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            def: "Something" [orcid:0000-0003-4423-4370]
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_7_comment(self) -> None:
        """Test appending a comment."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_comment("I like this record")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            comment: "I like this record"
            property_value: rdfs:comment "I like this record" xsd:string
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_8(self) -> None:
        """Test the XXX tag."""
        raise NotImplementedError

    def test_9_append_synonym(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            synonym: "L-lysine:NAD+ oxidoreductase" EXACT []
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            specificity="RELATED",
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            synonym: "L-lysine:NAD+ oxidoreductase" RELATED []
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase", specificity="RELATED", provenance=[CHARLIE]
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            synonym: "L-lysine:NAD+ oxidoreductase" RELATED [orcid:0000-0003-4423-4370]
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

        omo_dummy = SynonymTypeDef(reference=Reference(prefix="OMO", identifier="1234567"))
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            type=omo_dummy,
            provenance=[Reference(prefix="orcid", identifier="0000-0003-4423-4370")],
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            synonym: "L-lysine:NAD+ oxidoreductase" EXACT OMO:1234567 [orcid:0000-0003-4423-4370]
            """,
            term.iterate_obo_lines(
                ontology_prefix="go",
                typedefs={RO_DUMMY.pair: RO_DUMMY},
                synonym_typedefs={omo_dummy.pair: omo_dummy},
            ),
        )

    def test_9_append_synonym_missing_typedef(self) -> None:
        """Test appending a synonym."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_synonym(
            "L-lysine:NAD+ oxidoreductase",
            type=Reference(prefix="OMO", identifier="1234567"),
        )
        with self.assertLogs(level="INFO") as log:
            self.assert_lines(
                """\
                [Term]
                id: GO:0050069
                name: lysine dehydrogenase activity
                synonym: "L-lysine:NAD+ oxidoreductase" EXACT OMO:1234567 []
                """,
                term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
            )
        self.assertIn(
            "WARNING:pyobo.struct.struct:[go] synonym typedef not defined: OMO:1234567", log.output
        )

    def test_10_xref(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_xref(Reference(prefix="eccode", identifier="1.4.1.15"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            xref: eccode:1.4.1.15
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
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
        lines = dedent("""\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            xref: eccode:1.4.1.15 {sssom:confidence=0.99} ! lysine dehydrogenase
        """)
        self.assert_lines(
            lines,
            term.iterate_obo_lines(
                ontology_prefix="go",
                typedefs={
                    RO_DUMMY.pair: RO_DUMMY,
                    mapping_has_confidence.pair: mapping_has_confidence,
                    mapping_has_justification.pair: mapping_has_justification,
                    has_contributor.pair: has_contributor,
                },
            ),
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
        term = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            builtin=True,
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            builtin: true
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        term2 = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            builtin=False,
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            builtin: false
            """,
            term2.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_12_property_default_reference(self) -> None:
        """Test adding a replaced by."""
        r = default_reference("go", "hey")
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(r, Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: hey GO:1234569
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={r.pair: r}),
        )

    def test_12_property_literal(self) -> None:
        """Test emitting property literals."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_literal(RO_DUMMY, "value")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 "value" xsd:string
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_12_property_integer(self) -> None:
        """Test emitting property literals that were annotated as a boolean."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_integer(RO_DUMMY, 1234)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 "1234" xsd:integer
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_12_property_bool(self) -> None:
        """Test emitting property literals that were annotated as a boolean."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_boolean(RO_DUMMY, True)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 "true" xsd:boolean
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_12_property_year(self) -> None:
        """Test emitting property literals that were annotated as a year."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_year(RO_DUMMY, "1993")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 "1993" xsd:gYear
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_12_property_object(self) -> None:
        """Test emitting property literals."""
        term = Term(reference=LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(RO_DUMMY, Reference(prefix="hgnc", identifier="123"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 hgnc:123
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_13_parent(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_parent(Reference(prefix="GO", identifier="1234568"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            is_a: GO:1234568
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_14_intersection_of(self) -> None:
        """Test emitting intersection of."""
        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_intersection_of(Reference(prefix="CL", identifier="0000540", name="neuron"))
        term.append_intersection_of(
            part_of.reference,
            Reference(prefix="NCBITaxon", identifier="7955", name="zebrafish"),
        )
        lines = dedent("""\
            [Term]
            id: ZFA:0000134
            intersection_of: CL:0000540 ! neuron
            intersection_of: BFO:0000050 NCBITaxon:7955 ! part of zebrafish
        """)
        self.assert_lines(lines, term.iterate_obo_lines(ontology_prefix="zfa", typedefs={}))

    def test_15_union_of(self) -> None:
        """Test emitting union of."""
        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_union_of(Reference(prefix="GO", identifier="0"))
        term.append_union_of(Reference(prefix="GO", identifier="1"))
        lines = dedent("""\
            [Term]
            id: ZFA:0000134
            union_of: GO:0
            union_of: GO:1
        """)
        self.assert_lines(lines, term.iterate_obo_lines(ontology_prefix="zfa", typedefs={}))

    def test_16_equivalent_classes(self) -> None:
        """Test emitting equivalent classes."""
        term = Term(reference=Reference(prefix="ZFA", identifier="0000134"))
        term.append_equivalent_to(Reference(prefix="GO", identifier="0"))
        lines = dedent("""\
            [Term]
            id: ZFA:0000134
            equivalent_to: GO:0
        """)
        self.assert_lines(lines, term.iterate_obo_lines(ontology_prefix="zfa", typedefs={}))

    def test_17_disjoint_from_namespace(self) -> None:
        """Test the ``disjoint_from`` tag."""
        term = Term(
            reference=LYSINE_DEHYDROGENASE_ACT,
            disjoint_from=[
                Reference(prefix="GO", identifier="0000000"),
                Reference(prefix="GO", identifier="0000001"),
            ],
        )

        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            disjoint_from: GO:0000000
            disjoint_from: GO:0000001
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_18_relation(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_relationship(RO_DUMMY, Reference(prefix="eccode", identifier="1.4.1.15"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            relationship: RO:1234567 eccode:1.4.1.15
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_18_append_exact_match(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_exact_match(
            Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase")
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
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
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.annotate_object(
            exact_match,
            Reference(prefix="eccode", identifier="1.4.1.15", name="lysine dehydrogenase"),
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: skos:exactMatch eccode:1.4.1.15 ! exact match lysine dehydrogenase
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )

    def test_18_set_species(self) -> None:
        """Test emitting a relationship."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.set_species("9606", "Homo sapiens")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            relationship: RO:0002162 NCBITaxon:9606 ! in taxon Homo sapiens
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
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
        lines = dedent("""\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: skos:exactMatch eccode:1.4.1.15 {sssom:confidence=0.99, \
sssom:mapping_justification=semapv:UnspecifiedMatching} ! exact match lysine dehydrogenase
        """)
        self.assert_lines(
            lines,
            term.iterate_obo_lines(
                ontology_prefix="go",
                typedefs={
                    RO_DUMMY.pair: RO_DUMMY,
                    mapping_has_confidence.pair: mapping_has_confidence,
                    mapping_has_justification.pair: mapping_has_justification,
                    has_contributor.pair: has_contributor,
                },
            ),
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
        term.append_see_also_url("https://example.org/test")
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: rdfs:seeAlso "https://example.org/test" xsd:anyURI
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        self.assertEqual(
            "https://example.org/test",
            term.get_property(see_also),
        )

        self.assertEqual(
            ["https://example.org/test"],
            term.get_properties(see_also),
        )

    def test_18_see_also_double(self) -> None:
        """Test appending see also."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        with self.assertRaises(ValueError):
            term.append_see_also("something")

        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_see_also(Reference(prefix="hgnc", identifier="1234", name="dummy 1"))
        term.append_see_also(Reference(prefix="hgnc", identifier="1235", name="dummy 2"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: rdfs:seeAlso hgnc:1234 ! see also dummy 1
            property_value: rdfs:seeAlso hgnc:1235 ! see also dummy 2
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        self.assertEqual(
            [
                Reference(prefix="hgnc", identifier="1234", name="dummy 1").curie,
                Reference(prefix="hgnc", identifier="1235", name="dummy 2").curie,
            ],
            term.get_properties(see_also),
        )

        self.assertIsNone(term.get_relationship(exact_match))
        self.assertIsNone(term.get_species())

    def test_19_created_by(self) -> None:
        """Test the ``created_by`` tag."""

    def test_20_creation_date(self) -> None:
        """Test the ``creation_date`` tag."""

    def test_21_obsolete(self) -> None:
        """Test obsolete definition."""
        term = Term(LYSINE_DEHYDROGENASE_ACT, is_obsolete=True)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            is_obsolete: true
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

        term = Term(LYSINE_DEHYDROGENASE_ACT, is_obsolete=False)
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            is_obsolete: false
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={}),
        )

    def test_22_replaced_by(self) -> None:
        """Test adding a replaced by."""
        term = Term(LYSINE_DEHYDROGENASE_ACT)
        term.append_replaced_by(Reference(prefix="GO", identifier="1234569", name="dummy"))
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: IAO:0100001 GO:1234569 ! term replaced by dummy
            replaced_by: GO:1234569 ! dummy
            """,
            term.iterate_obo_lines(ontology_prefix="go", typedefs={RO_DUMMY.pair: RO_DUMMY}),
        )
