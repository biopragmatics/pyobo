# -*- coding: utf-8 -*-

"""Tests for PyOBO caches."""

import os
import unittest
from tempfile import TemporaryDirectory

import time

from pyobo.cache_utils import cached_mapping


class TestCaches(unittest.TestCase):
    """Tests for PyOBO cache decorators."""

    def test_mapping(self):
        """Test the mapping cache."""
        sleep_time = 3
        with TemporaryDirectory() as directory:
            path = os.path.join(directory, 'test.tsv')
            header = ['key', 'value']

            @cached_mapping(path=path, header=header)
            def _get_mapping():
                """Return mapping"""
                time.sleep(sleep_time)
                return dict(a='x', b='y', c='z')

            start_time = time.time()
            rv = _get_mapping()
            elapsed = time.time() - start_time
            self.assertGreater(elapsed, sleep_time)

            self.assertIsNotNone(rv)
            self.assertEqual(3, len(rv))
            self.assertEqual(dict(a='x', b='y', c='z'), rv)

            start_time = time.time()
            rv2 = _get_mapping()  # this time should be fast
            elapsed = time.time() - start_time
            self.assertLess(elapsed, sleep_time)

            self.assertIsNotNone(rv2)
            self.assertEqual(3, len(rv2))
            self.assertEqual(dict(a='x', b='y', c='z'), rv2)
