"""Mocks for PyOBO."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar
from unittest import mock

import pandas as pd

from pyobo.constants import XREF_COLUMNS

__all__ = [
    "get_mock_get_xrefs_df",
    "get_mock_id_alts_mapping",
    "get_mock_id_name_mapping",
    "get_mock_id_synonyms_mapping",
]


def get_mock_id_name_mapping(data: Mapping[str, Mapping[str, str]]) -> mock._patch:
    """Mock the :func:`pyobo.extract.get_id_name_mapping` function.

    :param data: A mapping from prefix to mappings of identifier to names.
    """
    return _replace_mapping_getter("pyobo.api.names.get_id_name_mapping", data)


def get_mock_id_synonyms_mapping(data: Mapping[str, Mapping[str, list[str]]]) -> mock._patch:
    """Mock the :func:`pyobo.extract.get_id_synonyms_mapping` function.

    :param data: A mapping from prefix to mappings of identifier to lists of synonyms.
    """
    return _replace_mapping_getter("pyobo.api.names.get_id_synonyms_mapping", data)


def get_mock_id_alts_mapping(data: Mapping[str, Mapping[str, list[str]]]) -> mock._patch:
    """Mock the :func:`pyobo.extract.get_id_to_alts` function.

    :param data: A mapping from prefix to mappings of identifier to lists of alternative
        identifiers.
    """
    return _replace_mapping_getter("pyobo.api.alts.get_id_to_alts", data)


X = TypeVar("X")


def _replace_mapping_getter(name: str, data: Mapping[str, Mapping[str, X]]) -> mock._patch:
    def _mock_get_data(prefix: str, **_kwargs) -> Mapping[str, X]:
        return data.get(prefix, {})

    return mock.patch(name, side_effect=_mock_get_data)


def get_mock_get_xrefs_df(
    df: list[tuple[str, str, str, str, str]] | pd.DataFrame,
) -> mock._patch:
    """Mock the :func:`pyobo.xrefsdb.xrefs_pipeline.get_xref_df` function.

    :param df: The dataframe to return when the function is called
    """
    if isinstance(df, list):
        df = pd.DataFrame(df, columns=XREF_COLUMNS)

    def _mock_get_xrefs_df(*_args, **_kwargs) -> pd.DataFrame:
        return df

    return mock.patch(
        "pyobo.resource_utils.ensure_inspector_javert_df", side_effect=_mock_get_xrefs_df
    )


def _make_mock_get_name(name: str, data: Mapping[str, Mapping[str, X]]) -> mock._patch:
    def _get_name(prefix: str, identifier: str) -> X | None:
        return data.get(prefix, {}).get(identifier)

    return mock.patch(name, side_effect=_get_name)
