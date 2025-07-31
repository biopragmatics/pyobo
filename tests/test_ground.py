"""Tests for PyOBO grounding."""

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
