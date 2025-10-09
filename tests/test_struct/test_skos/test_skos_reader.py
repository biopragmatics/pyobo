"""Test the SKOS reader."""

import unittest
from pathlib import Path

import curies
import rdflib

from pyobo.struct import Obo
from pyobo.struct.skosrdf import get_skos_ontology

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("test.ttl")


class TestSKOSReader(unittest.TestCase):
    """Test the SKOS reader."""

    def test_skos_reader(self) -> None:
        """Test the skos reader."""
        converter = curies.Converter.from_prefix_map(
            {
                "kim.hcrt": "https://w3id.org/kim/hcrt/",
                "dcterms": "http://purl.org/dc/terms/",
                "skos": "http://www.w3.org/2004/02/skos/core#",
            }
        )
        graph = rdflib.Graph()
        graph.parse(PATH)
        ontology = get_skos_ontology(graph, prefix="kim.hcrt", converter=converter)
        self.assertIsInstance(ontology, Obo)
