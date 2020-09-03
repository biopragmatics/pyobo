# -*- coding: utf-8 -*-

"""Tests for alternative identifiers."""

import unittest

from pyobo import get_name, get_name_by_curie, get_primary_curie, get_primary_identifier


class TestAltIds(unittest.TestCase):
    """Tests for alternative identifiers."""

    def test_get_primary(self):
        """Test upgrading an obsolete identifier."""
        primary_id = get_primary_identifier('go', '0001071')
        self.assertIsNotNone(primary_id)
        self.assertEqual('0003700', primary_id)
        name = get_name('go', '0001071')
        self.assertIsNotNone(name)
        self.assertEqual('DNA-binding transcription factor activity', name)

    def test_get_primary_by_curie(self):
        """Test upgrading an obsolete CURIE."""
        primary_curie = get_primary_curie('go:0001071')
        self.assertIsNotNone(primary_curie)
        self.assertEqual('go:0003700', primary_curie)
        name = get_name_by_curie('go:0001071')
        self.assertIsNotNone(name)
        self.assertEqual('DNA-binding transcription factor activity', name)

    def test_already_primary(self):
        """Test when you give a primary id."""
        primary_id = get_primary_identifier('go', '0003700')
        self.assertIsNotNone(primary_id)
        self.assertEqual('0003700', primary_id)
        name = get_name('go', '0003700')
        self.assertIsNotNone(name)
        self.assertEqual('DNA-binding transcription factor activity', name)

    def test_already_primary_by_curie(self):
        """Test when you give a primary CURIE."""
        primary_curie = get_primary_curie('go:0003700')
        self.assertIsNotNone(primary_curie)
        self.assertEqual('go:0003700', primary_curie)
        name = get_name_by_curie('go:0003700')
        self.assertIsNotNone(name)
        self.assertEqual('DNA-binding transcription factor activity', name)
