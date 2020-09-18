# -*- coding: utf-8 -*-

"""Mocks for PyOBO."""

from typing import List, Mapping, Tuple, TypeVar, Union
from unittest import mock

import pandas as pd

from pyobo.constants import XREF_COLUMNS

__all__ = [
    'get_mock_id_name_mapping',
    'get_mock_id_synonyms_mapping',
    'get_mock_get_xrefs_df',
]


def get_mock_id_name_mapping(data: Mapping[str, Mapping[str, str]]) -> mock.patch:
    """Mock the :func:`pyobo.extract.get_id_name_mapping` function.

    :param data: A mapping from prefix to mappings of identifier to names.
    """
    return _replace_mapping_getter('pyobo.extract.get_id_name_mapping', data)


def get_mock_id_synonyms_mapping(data: Mapping[str, Mapping[str, List[str]]]) -> mock.patch:
    """Mock the :func:`pyobo.extract.get_id_synonyms_mapping` function.

    :param data: A mapping from prefix to mappings of identifier to lists of synonyms.
    """
    return _replace_mapping_getter('pyobo.extract.get_id_synonyms_mapping', data)


def get_mock_get_xrefs_df(df: Union[List[Tuple[str, str, str, str, str]], pd.DataFrame]) -> mock.patch:
    """Mock the :func:`pyobo.xrefsdb.xrefs_pipeline.get_xref_df` function.

    :param df: The dataframe to return when the function is called
    """
    if isinstance(df, list):
        df = pd.DataFrame(df, columns=XREF_COLUMNS)

    def _mock_get_xrefs_df(*_args, **_kwargs) -> pd.DataFrame:
        return df

    return mock.patch('pyobo.xrefdb.xrefs_pipeline.get_xref_df', side_effect=_mock_get_xrefs_df)


X = TypeVar('X')


def _replace_mapping_getter(name: str, data: Mapping[str, X]) -> mock.patch:
    def _mock_get_id_synonyms_mapping(prefix: str) -> X:
        return data[prefix]

    return mock.patch(name, side_effect=_mock_get_id_synonyms_mapping)
