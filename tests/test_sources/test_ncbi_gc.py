"""Tests for NCBI GC."""

import unittest


class TestNCBIGC(unittest.TestCase):
    """Tests for NCBI GC."""

    @unittest.skip(reason="only run locally since this uses live data")
    def test_gc_prefixes(self) -> None:
        """Test GC returns the right prefixes."""
        from pyobo.sources.ncbi.ncbi_gc import NCBIGCGetter

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
