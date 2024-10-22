"""Tests for PyOBO."""

import unittest

import pandas as pd

import pyobo
from pyobo import get_filtered_xrefs, get_id_name_mapping, get_xrefs_df
from pyobo.constants import TARGET_ID, TARGET_PREFIX
from pyobo.mocks import get_mock_get_xrefs_df
from tests.constants import chebi_patch

_mock_rows = [
    ("hgnc", "6893", "ncbigene", "4137", "N/A"),
    ("hgnc", "6893", "ensembl", "ENSG00000186868", "N/A"),
]
mock_get_xrefs_df = get_mock_get_xrefs_df(_mock_rows)


class TestMapping(unittest.TestCase):
    """Test extracting information."""

    def test_get_names(self):
        """Test getting names."""
        with chebi_patch:
            id_to_name = get_id_name_mapping("chebi")
            for identifier in id_to_name:
                self.assertFalse(identifier.startswith("CHEBI"))
                self.assertFalse(identifier.startswith("CHEBI:"))
                self.assertFalse(identifier.startswith("chebi:"))
                self.assertFalse(identifier.startswith("chebi"))

    def test_get_xrefs(self):
        """Test getting xrefs."""
        with chebi_patch:
            df = get_xrefs_df("chebi")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(["chebi_id", TARGET_PREFIX, TARGET_ID], list(df.columns))

    def test_get_target_xrefs(self):
        """Test getting xrefs."""
        with chebi_patch:
            kegg_xrefs = get_filtered_xrefs("chebi", "kegg")

        for key, value in kegg_xrefs.items():
            self.assertFalse(key.startswith("CHEBI:"))
            self.assertFalse(key.startswith("CHEBI"))
            self.assertFalse(key.startswith("chebi:"))
            self.assertFalse(key.startswith("chebi"))
            self.assertFalse(value.startswith("KEGG:"))
            self.assertFalse(value.startswith("KEGG"))
            self.assertFalse(value.startswith("kegg:"))
            self.assertFalse(value.startswith("kegg"))

        self.assertIsInstance(kegg_xrefs, dict)

    @mock_get_xrefs_df
    def test_get_equivalent(self, _):
        """Test getting equivalent CURIEs."""
        mapt_curies = pyobo.get_equivalent("hgnc:6893")
        self.assertIn("ncbigene:4137", mapt_curies)
        self.assertIn("ensembl:ENSG00000186868", mapt_curies)
        self.assertNotIn("hgnc:6893", mapt_curies)
