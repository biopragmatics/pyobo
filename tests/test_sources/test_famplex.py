"""Tests for famplex."""

import unittest

from pyobo.xrefdb.sources.famplex import _get_famplex_df


class TestFamplex(unittest.TestCase):
    """Tests for famplex."""

    def test_mapping(self):
        """Test geting the mapping df."""
        df = _get_famplex_df(force=True)
        self.assertIsNotNone(df)

    @unittest.skip(reason="only run locally since this uses live data")
    def test_gc_prefixes(self) -> None:
        """Test GC returns the right prefixes."""
        from pyobo.sources.ncbi_gc import NCBIGCGetter

        prefix_map = NCBIGCGetter()._infer_prefix_map()
        self.assertEqual(
            sorted(
                {
                    "GO",
                    "gc",
                    "dcterms",
                    "NCBITaxon",
                    "orcid",
                    "obo",
                    "IAO",
                    "owl",
                    "rdf",
                    "rdfs",
                    "xsd",
                }
            ),
            sorted(prefix_map),
        )
