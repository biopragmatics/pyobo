"""Test iteration tools."""

import unittest

from curies import ReferenceTuple

from pyobo.sources.expasy import _parse_transfer
from pyobo.struct.reference import _pyobo_parse_curie
from pyobo.utils.iter import iterate_together


class TestStringUtils(unittest.TestCase):
    """Test string utilities."""

    def test_strip_prefix(self):
        """Test stripping prefixes works."""
        self.assertEqual(ReferenceTuple("go", "1234"), _pyobo_parse_curie("GO:1234"))
        self.assertEqual(ReferenceTuple("go", "1234"), _pyobo_parse_curie("go:1234"))

        self.assertIsNone(_pyobo_parse_curie("1234"))
        self.assertEqual(ReferenceTuple("go", "1234"), _pyobo_parse_curie("GO:GO:1234"))

        self.assertEqual(ReferenceTuple("pubmed", "1234"), _pyobo_parse_curie("pubmed:1234"))
        # Test remapping
        self.assertEqual(ReferenceTuple("pubmed", "1234"), _pyobo_parse_curie("pmid:1234"))
        self.assertEqual(ReferenceTuple("pubmed", "1234"), _pyobo_parse_curie("PMID:1234"))

        # Test resource-specific remapping
        self.assertIsNone(_pyobo_parse_curie("Thesaurus:C1234", strict=False))
        self.assertEqual(
            ReferenceTuple("ncit", "C1234"), _pyobo_parse_curie("Thesaurus:C1234", ontology="enm")
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
