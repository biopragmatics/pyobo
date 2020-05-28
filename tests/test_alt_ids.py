# -*- coding: utf-8 -*-

"""Tests for alternative identifiers."""

import unittest

from pyobo import get_primary_curie, get_primary_identifier


class TestAltIds(unittest.TestCase):
    """Tests for alternative identifiers."""

    def test_get_primary(self):
        """Test upgrading an obsolete identifier."""
        primary_id = get_primary_identifier('go', '0001071')
        self.assertIsNotNone(primary_id)
        self.assertEqual('0003700', primary_id)

        primary_curie = get_primary_curie('go:0001071')
        self.assertIsNotNone(primary_curie)
        self.assertEqual('go:0003700', primary_curie)

    def test_already_primary(self):
        """Test when you give a primary id."""
        primary_id = get_primary_identifier('go', '0003700')
        self.assertIsNotNone(primary_id)
        self.assertEqual('0003700', primary_id)

        primary_curie = get_primary_curie('go:0003700')
        self.assertIsNotNone(primary_curie)
        self.assertEqual('go:0003700', primary_curie)
