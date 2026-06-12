"""Test the SKOS reader."""

import unittest
from pathlib import Path

from curies import Converter
from curies import vocabulary as v

from pyobo.struct import Obo
from pyobo.struct.skos import read_skos

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("test.ttl")


class TestSKOSReader(unittest.TestCase):
    """Test the SKOS reader."""

    def test_skos_reader(self) -> None:
        """Test the skos reader."""
        converter = Converter.from_prefix_map(
            {
                "kim.hcrt": "https://w3id.org/kim/hcrt/",
                "dcterms": "http://purl.org/dc/terms/",
                "skos": "http://www.w3.org/2004/02/skos/core#",
            }
        )
        ontology = read_skos(PATH, prefix="kim.hcrt", converter=converter)
        self.assertIsInstance(ontology, Obo)

    def test_narrow_matches_rewired(self) -> None:
        """Test ISCED 2013."""
        url = "https://github.com/dini-ag-kim/vocabs-edu/raw/refs/heads/master/isced-2013.ttl"
        converter = Converter.from_prefix_map(
            {
                "isced2013": "https://w3id.org/kim/isced-2013/",
                "dcterms": "http://purl.org/dc/terms/",
                "skos": "http://www.w3.org/2004/02/skos/core#",
            }
        )
        ontology = read_skos(url, converter=converter)
        for term in ontology:
            self.assertEqual([], term.get_property_objects(v.narrow_match))
