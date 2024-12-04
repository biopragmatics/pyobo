"""Tests for PyOBO grounding."""

import unittest

import pyobo
from pyobo.mocks import get_mock_id_name_mapping, get_mock_id_synonyms_mapping

mock_id_name_mapping = get_mock_id_name_mapping(
    {
        "chebi": {
            "132964": "fluazifop-P-butyl",
        },
    }
)

mock_id_synonyms_mapping = get_mock_id_synonyms_mapping(
    {
        "chebi": {
            "132964": ["Fusilade II"],
        },
    }
)


class TestGround(unittest.TestCase):
    """Test grounding."""

    def test_ground(self):
        """Test grounding a ChEBI entry by name and synonym."""
        for query in ("Fusilade II", "fluazifop-P-butyl"):
            with self.subTest(query=query), mock_id_name_mapping, mock_id_synonyms_mapping:
                prefix, identifier, name = pyobo.ground("chebi", query)
                self.assertIsNotNone(prefix)
                self.assertIsNotNone(identifier)
                self.assertIsNotNone(name)
                self.assertEqual("chebi", prefix)
                self.assertEqual("132964", identifier)
                self.assertEqual("fluazifop-P-butyl", name)
