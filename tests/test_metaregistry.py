# -*- coding: utf-8 -*-

"""Test the curated registry's integrity."""

import unittest

from pyobo.registries import get_curated_registry


class TestCuratedRegistry(unittest.TestCase):
    """Test the curated registry's integrity."""

    def test_integrity(self):
        """Test the curated registry's integrity."""
        g = get_curated_registry()
        for prefix, entry in g.items():
            with self.subTest(prefix=prefix, msg='failed for prefix'):
                pass
                # TODO add tests for minimum metadata here
                # self.assertIn('', entry)
