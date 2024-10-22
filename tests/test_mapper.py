"""Test mapping program."""

import unittest

import pandas as pd

from pyobo import Canonicalizer
from pyobo.constants import XREF_COLUMNS
from pyobo.xrefdb.xrefs_pipeline import get_graph_from_xref_df


class TestCanonicalizer(unittest.TestCase):
    """Tests for the canonicalizer."""

    canonicalizer: Canonicalizer

    def setUp(self) -> None:
        """Set up a test dataframe for canonicalization."""
        df = pd.DataFrame(
            [
                # Cluster 1 - fully connected
                ["hgnc", "h1", "ensembl", "e1", "example_source"],
                ["hgnc", "h1", "omim", "o1", "example_source"],
                ["omim", "o1", "cds", "c1", "example_source"],
                # Cluster 2 - missing HGNC
                ["omim", "o2", "ensembl", "e2"],
                # Cluster 3 - irrelevant
                ["y", "y1", "z", "z1", "irrelevant_source"],
            ],
            columns=XREF_COLUMNS,
        )
        graph = get_graph_from_xref_df(df)
        priority = [
            "hgnc",
            "omim",
            "ensembl",
        ]
        self.canonicalizer = Canonicalizer(graph=graph, priority=priority)

    def test_priority(self):
        """Test lookup priority."""
        self.assertEqual(3, self.canonicalizer._key("hgnc:h1"))
        self.assertEqual(2, self.canonicalizer._key("omim:o1"))
        self.assertEqual(1, self.canonicalizer._key("ensembl:e1"))
        # Since CDS isn't there, it gets no priority at all
        self.assertEqual(None, self.canonicalizer._key("cds:c1"))

    def test_mapper(self):
        """Test mapping back to hgnc for cluster 1."""
        for curie in ["hgnc:h1", "ensembl:e1", "omim:o1", "cds:c1"]:
            with self.subTest(curie=curie):
                self.assertEqual("hgnc:h1", self.canonicalizer.canonicalize(curie))

        # Test a non-present node
        self.assertEqual("xxx:x1", self.canonicalizer.canonicalize("xxx:x1"))

        for curie in ["omim:o2", "ensembl:e2"]:
            with self.subTest(curie=curie):
                self.assertEqual("omim:o2", self.canonicalizer.canonicalize(curie))

        # Test a present node with no priority information
        self.assertEqual("y:y1", self.canonicalizer.canonicalize("y:y1"))
        self.assertEqual("z:z1", self.canonicalizer.canonicalize("z:z1"))
