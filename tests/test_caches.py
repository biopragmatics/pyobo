# -*- coding: utf-8 -*-

"""Tests for PyOBO caches."""

import os
import unittest
from tempfile import TemporaryDirectory

import time

from pyobo.cache_utils import cached_mapping
from pyobo.io_utils import open_map_tsv


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
            rv1 = _get_mapping()
            elapsed = time.time() - start_time
            self.assertGreater(elapsed, sleep_time)

            self._help_test_mapping(rv1)

            """Test cache"""
            rv3 = open_map_tsv(path)
            self._help_test_mapping(rv3)

            """Test reload"""

            start_time = time.time()
            rv2 = _get_mapping()  # this time should be fast
            elapsed = time.time() - start_time
            self.assertLess(elapsed, sleep_time)

            self._help_test_mapping(rv2)

    def _help_test_mapping(self, d):
        self.assertIsNotNone(d)
        self.assertEqual(3, len(d))
        self.assertEqual(dict(a='x', b='y', c='z'), d)
