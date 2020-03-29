# -*- coding: utf-8 -*-

"""High level API for extracting OBO content."""

from typing import List, Mapping

import pandas as pd

from .cache_utils import cached_df, cached_mapping, cached_multidict
from .getters import get
from .path_utils import prefix_directory_join
from .struct import Reference, TypeDef

__all__ = [
    'get_name_id_mapping',
    'get_id_name_mapping',
    'get_id_synonyms_mapping',
    'get_properties_df',
    'get_filtered_properties_df',
    'get_id_multirelations_mapping',
    'get_relations_df',
    'get_filtered_xrefs',
    'get_xrefs_df',
]


def get_id_name_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    path = prefix_directory_join(prefix, 'cache', f"{prefix}.mapping.tsv")

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'])
    def _get_id_name_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_id_name_mapping()

    return _get_id_name_mapping()


def get_name_id_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    return {
        name: identifier
        for identifier, name in get_id_name_mapping(prefix=prefix, **kwargs).items()
    }


def get_id_synonyms_mapping(prefix: str, **kwargs) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, 'cache', "synonyms.tsv")
    header = [f'{prefix}_id', 'synonym']

    @cached_multidict(path=path, header=header)
    def _get_multidict() -> Mapping[str, List[str]]:
        obo = get(prefix, **kwargs)
        return obo.get_id_synonyms_mapping()

    return _get_multidict()


def get_properties_df(prefix: str, **kwargs) -> pd.DataFrame:
    """Extract properties."""
    path = prefix_directory_join(prefix, 'cache', "properties.tsv")

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_properties_df()

    return _df_getter()


def get_filtered_properties_df(prefix: str, prop: str, **kwargs) -> pd.DataFrame:
    """Extract a single property for each term."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_df(prop)

    return _df_getter()


def get_relations_df(prefix: str, **kwargs) -> pd.DataFrame:
    """Get all relations from the OBO."""
    path = prefix_directory_join(prefix, 'cache', 'relations.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_relations_df()

    return _df_getter()


def get_id_multirelations_mapping(prefix: str, type_def: TypeDef, **kwargs) -> Mapping[str, List[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    obo = get(prefix, **kwargs)
    return obo.get_id_multirelations_mapping(type_def)


def get_filtered_xrefs(prefix: str, xref_prefix: str, **kwargs) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    path = prefix_directory_join(prefix, 'cache', 'xrefs', f"{xref_prefix}.tsv")
    header = [f'{prefix}_id', f'{xref_prefix}_id']

    @cached_mapping(path=path, header=header)
    def _get_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_xrefs_mapping(xref_prefix)

    return _get_mapping()


def get_xrefs_df(prefix: str, **kwargs) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_directory_join(prefix, 'cache', "mappings.tsv")

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_xrefs_df()

    return _df_getter()
