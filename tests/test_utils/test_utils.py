"""Test iteration tools."""

import unittest

from pyobo.identifier_utils import (
    NotCURIEError,
    UnregisteredPrefixError,
    _parse_str_or_curie_or_uri_helper,
)
from pyobo.sources.expasy import _parse_transfer
from pyobo.utils.iter import iterate_together


class TestStringUtils(unittest.TestCase):
    """Test string utilities."""

    def test_strip_prefix(self):
        """Test stripping prefixes works."""
        self.assertEqual(("go", "1234567"), _parse_str_or_curie_or_uri_helper("GO:1234567").pair)
        self.assertEqual(("go", "1234567"), _parse_str_or_curie_or_uri_helper("go:1234567").pair)

        self.assertIsInstance(_parse_str_or_curie_or_uri_helper("1234567"), NotCURIEError)
        self.assertEqual(("go", "1234567"), _parse_str_or_curie_or_uri_helper("GO:GO:1234567").pair)

        self.assertEqual(("pubmed", "1234"), _parse_str_or_curie_or_uri_helper("pubmed:1234").pair)
        # Test remapping
        self.assertEqual(("pubmed", "1234"), _parse_str_or_curie_or_uri_helper("pmid:1234").pair)
        self.assertEqual(("pubmed", "1234"), _parse_str_or_curie_or_uri_helper("PMID:1234").pair)

        # Test resource-specific remapping
        self.assertIsInstance(
            _parse_str_or_curie_or_uri_helper("Thesaurus:C1234"), UnregisteredPrefixError
        )
        self.assertEqual(
            ("ncit", "C1234"),
            _parse_str_or_curie_or_uri_helper("Thesaurus:C1234", ontology_prefix="enm").pair,
        )

        # parsing IRIs
        self.assertEqual(
            ("chebi", "1234"),
            _parse_str_or_curie_or_uri_helper("http://purl.obolibrary.org/obo/CHEBI_1234").pair,
        )

    def test_parse_eccode_transfer(self):
        """Test parse_eccode_transfer."""
        self.assertEqual(
            ["1.1.1.198", "1.1.1.227", "1.1.1.228"],
            _parse_transfer("Transferred entry: 1.1.1.198, 1.1.1.227 and 1.1.1.228."),
        )
        self.assertEqual(
            ["1.1.1.198", "1.1.1.227", "1.1.1.228"],
            _parse_transfer("Transferred entry: 1.1.1.198, 1.1.1.227 and 1.1.1.228"),
        )
        self.assertEqual(
            ["1.1.1.198", "1.1.1.227", "1.1.1.228"],
            _parse_transfer("Transferred entry: 1.1.1.198, 1.1.1.227, and 1.1.1.228"),
        )
        self.assertEqual(
            ["1.1.1.198", "1.1.1.228"],
            _parse_transfer("Transferred entry: 1.1.1.198 and 1.1.1.228."),
        )


class TestIterate(unittest.TestCase):
    """Test iteration tools."""

    def test_a(self):
        """Test iterating two iterables together."""
        a = iter(
            [
                ("1", "a"),
                ("2", "b"),
                ("3", "c"),
            ]
        )
        b = iter(
            [
                ("1", "a1"),
                ("1", "a2"),
                ("2", "b1"),
                ("3", "c1"),
                ("3", "c2"),
            ]
        )
        rv = [
            ("1", "a", ["a1", "a2"]),
            ("2", "b", ["b1"]),
            ("3", "c", ["c1", "c2"]),
        ]

        r = iterate_together(a, b)
        self.assertNotIsInstance(r, list)
        self.assertEqual(rv, list(r))
