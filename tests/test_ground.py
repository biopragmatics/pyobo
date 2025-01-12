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
                result = pyobo.ground("chebi", query)
                self.assertIsNotNone(result)
                self.assertEqual("chebi", result.prefix)
                self.assertEqual("132964", result.identifier)
                self.assertEqual("fluazifop-P-butyl", result.name)
