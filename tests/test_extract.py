# -*- coding: utf-8 -*-

"""Tests for PyOBO."""

import unittest

import pandas as pd

import pyobo
from pyobo import get_filtered_xrefs, get_id_name_mapping, get_xrefs_df
from pyobo.mocks import get_mock_get_xrefs_df
from tests.constants import TEST_CHEBI_OBO_PATH

_mock_rows = [
    ('hgnc', '6893', 'ncbigene', '4137', 'N/A'),
    ('hgnc', '6893', 'ensembl', 'ENSG00000186868', 'N/A'),
]
mock_get_xrefs_df = get_mock_get_xrefs_df(_mock_rows)


class TestMapping(unittest.TestCase):
    """Test extracting information."""

    def test_get_names(self):
        """Test getting names."""
        id_to_name = get_id_name_mapping('chebi', url=TEST_CHEBI_OBO_PATH, local=True)
        for identifier in id_to_name:
            self.assertFalse(identifier.startswith('CHEBI'))
            self.assertFalse(identifier.startswith('CHEBI:'))
            self.assertFalse(identifier.startswith('chebi:'))
            self.assertFalse(identifier.startswith('chebi'))

    def test_get_xrefs(self):
        """Test getting xrefs."""
        df = get_xrefs_df('chebi', url=TEST_CHEBI_OBO_PATH, local=True)
        self.assertIsInstance(df, pd.DataFrame)

        for key, value in df[['source_ns', 'source_id']].values:  # no need for targets since are external
            self.assertFalse(value.startswith(key))
            self.assertFalse(value.lower().startswith(key.lower()), msg=f'Bad value: {value}')
            self.assertFalse(value.startswith(f'{key}:'))
            self.assertFalse(value.lower().startswith(f'{key.lower()}:'))

    def test_get_target_xrefs(self):
        """Test getting xrefs."""
        kegg_xrefs = get_filtered_xrefs('chebi', 'kegg', url=TEST_CHEBI_OBO_PATH, local=True)
        print(kegg_xrefs)

        for key, value in kegg_xrefs.items():
            self.assertFalse(key.startswith('CHEBI:'))
            self.assertFalse(key.startswith('CHEBI'))
            self.assertFalse(key.startswith('chebi:'))
            self.assertFalse(key.startswith('chebi'))
            self.assertFalse(value.startswith('KEGG:'))
            self.assertFalse(value.startswith('KEGG'))
            self.assertFalse(value.startswith('kegg:'))
            self.assertFalse(value.startswith('kegg'))

        self.assertIsInstance(kegg_xrefs, dict)

    @mock_get_xrefs_df
    def test_get_equivalent(self, _):
        """Test getting equivalent CURIEs."""
        mapt_curies = pyobo.get_equivalent('hgnc:6893')
        self.assertIn('ncbigene:4137', mapt_curies)
        self.assertIn('ensembl:ENSG00000186868', mapt_curies)
        self.assertNotIn('hgnc:6893', mapt_curies)
