# -*- coding: utf-8 -*-

"""Test iteration tools."""

import unittest

from pyobo.iter_utils import iterate_together


class TestIterate(unittest.TestCase):
    """Test iteration tools."""

    def test_a(self):
        """Test iterating two iterables together."""
        a = iter([
            ('1', 'a'),
            ('2', 'b'),
            ('3', 'c'),
        ])
        b = iter([
            ('1', 'a1'),
            ('1', 'a2'),
            ('2', 'b1'),
            ('3', 'c1'),
            ('3', 'c2'),
        ])
        rv = [
            ('1', 'a', ['a1', 'a2']),
            ('2', 'b', ['b1']),
            ('3', 'c', ['c1', 'c2']),
        ]

        r = iterate_together(a, b)
        self.assertNotIsInstance(r, list)
        self.assertEqual(rv, list(r))
