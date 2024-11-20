"""Tests for the OBO data structures."""

import unittest
from collections.abc import Iterable
from textwrap import dedent

from pyobo import Obo, Reference
from pyobo.struct.struct import BioregistryError, SynonymTypeDef, Term, TypeDef


class Nope(Obo):
    """A class that will fail."""

    ontology = "nope"

    def iter_terms(self, force: bool = False):
        """Do not do anything."""


class TestStruct(unittest.TestCase):
    """Tests for the OBO data structures."""

    def test_invalid_prefix(self):
        """Test raising an error when an invalid prefix is used."""
        with self.assertRaises(BioregistryError):
            Nope()

    def test_reference_validation(self):
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
        self.assertEqual('synonymtypedef: OMO:0003012 "acronym"', s1.to_obo())

        s2 = SynonymTypeDef(reference=r2)
        self.assertEqual("synonymtypedef: OMO:0003012", s2.to_obo())

        s3 = SynonymTypeDef(reference=r1, specificity="EXACT")
        self.assertEqual('synonymtypedef: OMO:0003012 "acronym" EXACT', s3.to_obo())

        s4 = SynonymTypeDef(reference=r2, specificity="EXACT")
        self.assertEqual("synonymtypedef: OMO:0003012 EXACT", s4.to_obo())

    def assert_lines(self, text: str, lines: Iterable[str]) -> None:
        """Assert the lines are equal."""
        self.assertEqual(dedent(text).strip(), "\n".join(lines).strip())

    def test_term(self):
        """Test emitting properties."""
        term = Term(
            reference=Reference(
                prefix="GO", identifier="0050069", name="lysine dehydrogenase activity"
            ),
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            """,
            term.iterate_obo_lines(ontology_prefix="GO", typedefs={}),
        )

        def _str(value: str) -> tuple[str, Reference]:
            return value, Reference(prefix="xsd", identifier="string")

        typedef = TypeDef(reference=Reference.from_curie("RO:1234567"))
        term = Term(
            reference=Reference(
                prefix="GO", identifier="0050069", name="lysine dehydrogenase activity"
            ),
            annotations_literal={
                typedef.reference: [_str("value")],
            },
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: RO:1234567 "value" xsd:string
            """,
            term.iterate_obo_lines(ontology_prefix="GO", typedefs={typedef.pair: typedef}),
        )

        term = Term(
            reference=Reference(
                prefix="GO", identifier="0050069", name="lysine dehydrogenase activity"
            ),
            relationships={
                typedef.reference: [Reference(prefix="eccode", identifier="1.1.1.1")],
            },
        )
        self.assert_lines(
            """\
            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            relationship: RO:1234567 eccode:1.1.1.1
            """,
            term.iterate_obo_lines(ontology_prefix="GO", typedefs={typedef.pair: typedef}),
        )
