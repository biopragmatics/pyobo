"""Tests for NER wrapper."""

import importlib.util
import unittest

import pyobo


class TestGround(unittest.TestCase):
    """Test grounding."""

    def test_ground(self):
        """Test grounding a TAXRANK entry by name and synonym."""
        result = pyobo.ground("taxrank", "biovariety", cache=False)
        self.assertIsNotNone(result)
        self.assertEqual("taxrank", result.prefix)
        self.assertEqual("0000032", result.identifier)
        self.assertEqual("bio-variety", result.name)

    @unittest.skipUnless(
        importlib.util.find_spec("scispacy"),
        reason="scispacy is required to run this test case.",
    )
    def test_scispacy_knowledgebase(self) -> None:
        """Test loading a small ontology via PyOBO."""
        kb = pyobo.get_scispacy_knowledgebase("taxrank", cache=False)
        # this might grow over time
        self.assertLessEqual(73, len(kb.cui_to_entity))
