# -*- coding: utf-8 -*-

"""High level API for extracting OBO content."""

import os
from functools import lru_cache
from typing import List, Mapping, Optional, Tuple, Union

import pandas as pd

from .cache_utils import cached_df, cached_mapping, cached_multidict
from .constants import GLOBAL_SKIP, PYOBO_HOME
from .getters import get
from .identifier_utils import normalize_curie
from .path_utils import prefix_directory_join
from .registries import NOT_AVAILABLE_AS_OBO, OBSOLETE
from .struct import Reference, TypeDef, get_reference_tuple

__all__ = [
    # Nomenclature
    'get_name_id_mapping',
    'get_id_name_mapping',
    # Synonyms
    'get_id_synonyms_mapping',
    # Properties
    'get_properties_df',
    'get_filtered_properties_df',
    'get_filtered_properties_mapping',
    # Relations
    'get_filtered_relations_df',
    'get_id_multirelations_mapping',
    'get_relations_df',
    # Xrefs
    'get_filtered_xrefs',
    'get_xrefs_df',
    # misc
    'iter_cached_obo',
]


def get_name_by_curie(curie: str) -> Optional[str]:
    """Get the name for a CURIE, if possible."""
    prefix, identifier = normalize_curie(curie)
    if prefix and identifier:
        return get_name(prefix, identifier)


def get_name(prefix: str, identifier: str) -> Optional[str]:
    """Get the name for an entity."""
    id_name = get_id_name_mapping(prefix)
    if id_name:
        return id_name.get(identifier)


@lru_cache()
def get_id_name_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == 'ncbigene':
        from .sources.ncbigene import get_ncbigene_id_to_name_mapping
        return get_ncbigene_id_to_name_mapping()
    elif prefix == 'taxonomy':
        prefix = 'ncbitaxon'

    path = prefix_directory_join(prefix, 'cache', "names.tsv")

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'])
    def _get_id_name_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_id_name_mapping()

    return _get_id_name_mapping()


@lru_cache()
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
        df = obo.get_properties_df()
        df.dropna(inplace=True)
        return df

    return _df_getter()


def get_filtered_properties_mapping(prefix: str, prop: str, **kwargs) -> Mapping[str, str]:
    """Extract a single property for each term as a dictionary."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")

    @cached_mapping(path=path, header=[f'{prefix}_id', prop])
    def _mapping_getter() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_mapping(prop)

    return _mapping_getter()


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


def get_filtered_relations_df(
    prefix: str,
    relation: Union[Reference, TypeDef, Tuple[str, str]],
    **kwargs,
) -> pd.DataFrame:
    """Get all of the given relation."""
    relation = get_reference_tuple(relation)
    path = prefix_directory_join(prefix, 'cache', 'relations', f'{relation[0]}:{relation[1]}.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_relations_df(relation)

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
    path = prefix_directory_join(prefix, 'cache', 'xrefs.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_xrefs_df()

    return _df_getter()


def iter_cached_obo() -> List[Tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(PYOBO_HOME):
        if prefix in GLOBAL_SKIP or prefix in NOT_AVAILABLE_AS_OBO or prefix in OBSOLETE:
            continue
        d = os.path.join(PYOBO_HOME, prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith('.obo'):
                p = os.path.join(d, x)
                yield prefix, p
