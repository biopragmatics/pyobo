"""Tests for the reader."""

import datetime
import unittest
from io import StringIO
from textwrap import dedent

from obonet import read_obo

from pyobo import Obo, Term
from pyobo.reader import from_obonet, get_first_nonescaped_quote
from pyobo.struct import default_reference
from pyobo.struct.typedef import TypeDef, is_conjugate_base_of


def _read(text: str, *, strict: bool = True) -> Obo:
    text = dedent(text).strip()
    io = StringIO()
    io.write(text)
    io.seek(0)
    graph = read_obo(io)
    return from_obonet(graph, strict=strict)


class TestUtils(unittest.TestCase):
    """Test utilities for the reader."""

    def test_first_nonescaped_quote(self):
        """Test finding the first non-escaped double quote."""
        self.assertEqual(0, get_first_nonescaped_quote('"'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc"'))
        self.assertEqual(2, get_first_nonescaped_quote('\\""'))
        self.assertEqual(3, get_first_nonescaped_quote('abc"'))
        self.assertEqual(3, get_first_nonescaped_quote('abc""'))
        self.assertIsNone(get_first_nonescaped_quote("abc"))
        self.assertIsNone(get_first_nonescaped_quote('abc\\"'))
        self.assertIsNone(get_first_nonescaped_quote('\\"hello\\"'))


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

    def get_only_term(self, ontology: Obo) -> Term:
        """Assert there is only a single term in the ontology and return it."""
        terms = list(ontology.iter_terms())
        self.assertEqual(1, len(terms))
        term = terms[0]
        return term

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

        term = self.get_only_term(ontology)
        self.assertEqual("Test definition", term.definition)
        self.assertEqual(1, len(term.xrefs))
        xref = term.xrefs[0]
        self.assertEqual("drugbank:DB1234567", xref.curie)

    def test_relationship_qualified_undefined(self) -> None:
        """Test parsing a relationship that's loaded in the defaults."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: RO:0018033 CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_relationship_qualified_defined(self) -> None:
        """Test relationship parsing that's defined."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: RO:0018033 CHEBI:5678

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_relationship_unqualified(self) -> None:
        """Test relationship parsing that relies on default referencing."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: is_conjugate_base_of CHEBI:5678

            [Typedef]
            id: is_conjugate_base_of
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.get_relationship(is_conjugate_base_of))
        r = default_reference("chebi", "is_conjugate_base_of")
        td = TypeDef(reference=r)
        reference = term.get_relationship(td)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_node_unparsable(self) -> None:
        """Test loading an ontology with unparsable nodes.."""
        ontology = _read(
            """\
            ontology: chebi

            [Term]
            id: nope:1234
        """,
            strict=False,
        )
        self.assertEqual(0, len(list(ontology.iter_terms())))

    def test_malformed_typedef(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        with self.assertRaises(KeyError) as exc:
            _read("""\
                ontology: chebi

                [Typedef]
                name: nope
            """)
        self.assertEqual("typedef is missing an `id`", exc.exception.args[0])

    def test_typedef_xref(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        ontology = _read("""\
            ontology: chebi

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
            xref: debio:0000010
        """)
        self.assertEqual(1, len(ontology.typedefs))
        self.assertEqual(is_conjugate_base_of.pair, ontology.typedefs[0].pair)

    def test_definition_missing_start_quote(self) -> None:
        """Test parsing a definition missing a starting quote."""
        with self.assertRaises(ValueError) as exc:
            _read("""\
                ontology: chebi

                [Term]
                id: CHEBI:1234
                name: Test Name
                def: malformed definition without quotes
            """)
        self.assertEqual(
            "[chebi:1234] definition does not start with a quote", exc.exception.args[0]
        )

    def test_definition_missing_end_quote(self) -> None:
        """Test parsing a definition missing an ending quote."""
        with self.assertRaises(ValueError) as exc:
            _read("""\
                ontology: chebi

                [Term]
                id: CHEBI:1234
                name: Test Name
                def: "malformed definition without quotes
            """)
        self.assertEqual(
            '[chebi:1234] could not parse definition: "malformed definition without quotes',
            exc.exception.args[0],
        )
