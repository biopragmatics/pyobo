"""Tests for the reader."""

import datetime
import unittest
from io import StringIO
from textwrap import dedent

from obonet import read_obo

from pyobo import Obo
from pyobo.reader import from_obonet


def _read(text: str) -> Obo:
    text = dedent(text).strip()
    io = StringIO()
    io.write(text)
    io.seek(0)
    graph = read_obo(io)
    return from_obonet(graph)


class TestReader(unittest.TestCase):
    """Test the reader."""

    def test_unknown_ontology_prefix(self) -> None:
        """Test an ontology with an unknown prefix."""
        with self.assertRaises(ValueError) as exc:
            _read("""\
                ontology: nope

                [Term]
                id: CHEBI:1234
            """)
        self.assertEqual("unknown prefix: nope", exc.exception.args[0])

    def test_missing_date_version(self) -> None:
        """Test an ontology with a missing date and version."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    def test_bad_date_format(self) -> None:
        """Test an ontology with a malformed date and no version."""
        ontology = _read("""\
            ontology: chebi
            date: aabbccddeee

            [Term]
            id: CHEBI:1234
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    def test_date_no_version(self) -> None:
        """Test an ontology with a date but no version."""
        ontology = _read("""\
            ontology: chebi
            date: 20:11:2024 18:44

            [Term]
            id: CHEBI:1234
        """)
        self.assertEqual(datetime.datetime(2024, 11, 20, 18, 44), ontology.date)
        self.assertEqual("2024-11-20", ontology.data_version)

    def test_minimal(self) -> None:
        """Test an ontology with a version but no date."""
        ontology = _read("""\
            data-version: 185
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            def: "Test definition" [orcid:1234-1234-1234]
            xref: drugbank:DB1234567
        """)
        self.assertEqual([], ontology.typedefs)
        self.assertEqual([], ontology.synonym_typedefs)
        terms = list(ontology.iter_terms())
        self.assertEqual(1, len(terms))

        term = terms[0]
        self.assertEqual("Test definition", term.definition)
        self.assertEqual(1, len(term.xrefs))
        xref = term.xrefs[0]
        self.assertEqual("drugbank:DB1234567", xref.curie)
