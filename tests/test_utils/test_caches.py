"""Tests for PyOBO caches."""

import os
import time
import unittest
from tempfile import TemporaryDirectory

from pyobo.utils.cache import cached_mapping, cached_multidict
from pyobo.utils.io import open_map_tsv, open_multimap_tsv

sleep_time = 3


class TestCaches(unittest.TestCase):
    """Tests for PyOBO cache decorators."""

    def test_mapping(self):
        """Test the mapping cache."""
        with TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.tsv")
            header = ["key", "value"]

            @cached_mapping(path=path, header=header)
            def _get_mapping():
                time.sleep(sleep_time)
                return {"a": "x", "b": "y", "c": "z"}

            start_time = time.time()
            rv1 = _get_mapping()
            elapsed = time.time() - start_time
            self.assertGreater(elapsed, sleep_time)

            self._help_test_mapping(rv1)

            # Test cache
            rv3 = open_map_tsv(path)
            self._help_test_mapping(rv3)

            # Test reload
            start_time = time.time()
            rv2 = _get_mapping()  # this time should be fast
            elapsed = time.time() - start_time
            self.assertLess(elapsed, sleep_time)

            self._help_test_mapping(rv2)

    def _help_test_mapping(self, d):
        self.assertIsNotNone(d)
        self.assertEqual(3, len(d))
        self.assertEqual({"a": "x", "b": "y", "c": "z"}, d)

    def test_multidict(self):
        """Test caching a multidict."""
        with TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.tsv")
            header = ["key", "value"]

            @cached_multidict(path=path, header=header)
            def _get_multidict():
                time.sleep(sleep_time)
                return {"a": ["a1", "a2"], "b": ["b1"], "c": ["c1", "c2"]}

            start_time = time.time()
            rv1 = _get_multidict()
            elapsed = time.time() - start_time
            self.assertGreater(elapsed, sleep_time)

            self._help_test_multidict(rv1)

            # Test cache
            rv3 = open_multimap_tsv(path)
            self._help_test_multidict(rv3)

            # Test reload
            start_time = time.time()
            rv2 = _get_multidict()  # this time should be fast
            elapsed = time.time() - start_time
            self.assertLess(elapsed, sleep_time)

            self._help_test_multidict(rv2)

    def _help_test_multidict(self, d):
        self.assertIsNotNone(d)
        self.assertEqual(3, len(d))
        self.assertEqual({"a": ["a1", "a2"], "b": ["b1"], "c": ["c1", "c2"]}, d)
