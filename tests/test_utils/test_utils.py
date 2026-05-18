"""Test iteration tools."""

import unittest

from curies import Reference

from pyobo.identifier_utils import (
    NotCURIEError,
    UnregisteredPrefixError,
    _parse_str_or_curie_or_uri_helper,
)
from pyobo.sources.expasy import _parse_transfer
from pyobo.utils.iter import iterate_together


class TestStringUtils(unittest.TestCase):
    """Test string utilities."""

    def assert_pair(
        self, expected: tuple[str, str], curie: str, ontology_prefix: str | None = None
    ) -> None:
        """Test a pair is parsed properly."""
        xx = _parse_str_or_curie_or_uri_helper(curie, ontology_prefix=ontology_prefix)
        if not isinstance(xx, Reference):
            raise self.fail()
        self.assertEqual(expected, xx.pair)

    def test_strip_prefix(self) -> None:
        """Test stripping prefixes works."""
        self.assert_pair(("go", "1234567"), "GO:1234567")
        self.assert_pair(("go", "1234567"), "go:1234567")

        self.assertIsInstance(_parse_str_or_curie_or_uri_helper("1234567"), NotCURIEError)
        self.assert_pair(("go", "1234567"), "GO:GO:1234567")

        self.assert_pair(("pubmed", "1234"), "pubmed:1234")
        # Test remapping
        self.assert_pair(("pubmed", "1234"), "pmid:1234")
        self.assert_pair(("pubmed", "1234"), "PMID:1234")

        # Test resource-specific remapping
        self.assertIsInstance(
            _parse_str_or_curie_or_uri_helper("Thesaurus:C1234"), UnregisteredPrefixError
        )
        self.assert_pair(
            ("ncit", "C1234"),
            "Thesaurus:C1234",
            ontology_prefix="enm",
        )

        # parsing IRIs
        self.assert_pair(
            ("chebi", "1234"),
            "http://purl.obolibrary.org/obo/CHEBI_1234",
        )

    def test_parse_eccode_transfer(self) -> None:
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

    def test_a(self) -> None:
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
