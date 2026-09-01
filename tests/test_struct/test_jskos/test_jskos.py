"""Test JSKOS."""

import unittest

import curies

from pyobo.struct.jskos_utils import read_jskos

URL = "https://skohub.io/KDSF-FFK/kdsf-ffk/heads/main/w3id.org/kdsf-ffk/index.json"


class TestJSKOS(unittest.TestCase):
    """Test JSKOS."""

    def test_jskos(self) -> None:
        """Test JSKOS."""
        converter = curies.Converter.from_prefix_map(
            {
                "ksdf.fkk": "https://w3id.org/kdsf-ffk/",
            }
        )
        ontology = read_jskos(prefix="ksdf.fkk", path=URL, converter=converter)
        names = ontology.get_id_name_mapping()
        self.assertIn("ArbeitUndWirtschaft", names)
        self.assertIn("Work and Economy", names["ArbeitUndWirtschaft"])
