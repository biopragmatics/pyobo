"""Tests for famplex."""

import unittest

from pyobo.xrefdb.sources.famplex import _get_famplex_df


class TestFamplex(unittest.TestCase):
    """Tests for famplex."""

    def test_mapping(self):
        """Test geting the mapping df."""
        df = _get_famplex_df(force=True)
        self.assertIsNotNone(df)
