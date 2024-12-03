"""Test iteration tools."""

import unittest

from pyobo.identifier_utils import normalize_curie
from pyobo.sources.expasy import _parse_transfer
from pyobo.utils.iter import iterate_together


class TestStringUtils(unittest.TestCase):
    """Test string utilities."""

    def test_strip_prefix(self):
        """Test stripping prefixes works."""
        self.assertEqual(("go", "1234"), normalize_curie("GO:1234"))
        self.assertEqual(("go", "1234"), normalize_curie("go:1234"))

        self.assertEqual((None, None), normalize_curie("1234"))
        self.assertEqual(("go", "1234"), normalize_curie("GO:GO:1234"))

        self.assertEqual(("pubmed", "1234"), normalize_curie("pubmed:1234"))
        # Test remapping
        self.assertEqual(("pubmed", "1234"), normalize_curie("pmid:1234"))
        self.assertEqual(("pubmed", "1234"), normalize_curie("PMID:1234"))

        # Test resource-specific remapping
        self.assertEqual((None, None), normalize_curie("Thesaurus:C1234", strict=False))
        self.assertEqual(
            ("ncit", "C1234"), normalize_curie("Thesaurus:C1234", ontology_prefix="enm")
        )

        # parsing IRIs
        self.assertEqual(
            ("chebi", "1234"), normalize_curie("http://purl.obolibrary.org/obo/CHEBI_1234")
        )

        self.assertEqual(
            ("pubmed", "15559952"),
            normalize_curie("url:https://www.ncbi.nlm.nih.gov/pubmed/15559952"),
        )
        self.assertEqual(
            ("pubmed", "15559952"),
            normalize_curie(r"url:https\://www.ncbi.nlm.nih.gov/pubmed/15559952"),
        )
        self.assertEqual(
            ("pubmed", "15559952"),
            normalize_curie(r"url:https\://pubmed.ncbi.nlm.nih.gov/15559952/"),
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
