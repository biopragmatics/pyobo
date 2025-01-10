"""Tests for OBO Graphs."""

import unittest

from pyobo import Reference, Term
from pyobo.struct.struct import make_ad_hoc_ontology


class TestOBOGraph(unittest.TestCase):
    """Tests for OBO graph conversion."""

    def test_version(self) -> None:
        """Test that version makes a round trip."""
        version = "1.0"
        term = Term(reference=Reference(prefix="GO", identifier="0000001"))
        ontology = make_ad_hoc_ontology(
            _ontology="go",
            _data_version=version,
            terms=[term],
        )
        graph = ontology.get_graph()
        self.assertEqual(version, graph.version)
