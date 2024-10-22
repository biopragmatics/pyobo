"""High-level API for properties."""

import logging
import os
from collections.abc import Mapping
from typing import Optional

import pandas as pd

from .utils import get_version
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_df, cached_mapping, cached_multidict
from ..utils.io import multidict
from ..utils.path import prefix_cache_join

__all__ = [
    "get_properties_df",
    "get_filtered_properties_df",
    "get_filtered_properties_mapping",
    "get_filtered_properties_multimapping",
    "get_property",
    "get_properties",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_properties_df(
    prefix: str, *, force: bool = False, version: Optional[str] = None
) -> pd.DataFrame:
    """Extract properties.

    :param prefix: the resource to load
    :param force: should the resource be re-downloaded, re-parsed, and re-cached?
    :returns: A dataframe with the properties
    """
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="properties.tsv", version=version)

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if force:
            logger.info("[%s] forcing reload for properties", prefix)
        else:
            logger.info("[%s] no cached properties found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        df = ontology.get_properties_df()
        df.dropna(inplace=True)
        return df

    return _df_getter()


@wrap_norm_prefix
def get_filtered_properties_mapping(
    prefix: str,
    prop: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    version: Optional[str] = None,
) -> Mapping[str, str]:
    """Extract a single property for each term as a dictionary.

    :param prefix: the resource to load
    :param prop: the property to extract
    :param use_tqdm: should a progress bar be shown?
    :param force: should the resource be re-downloaded, re-parsed, and re-cached?
    :returns: A mapping from identifier to property value
    """
    df = get_properties_df(prefix=prefix, force=force, version=version)
    df = df[df["property"] == prop]
    return dict(df[[f"{prefix}_id", "value"]].values)

    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, "properties", name=f"{prop}.tsv", version=version)
    all_properties_path = prefix_cache_join(prefix, name="properties.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", prop], force=force)
    def _mapping_getter() -> Mapping[str, str]:
        if os.path.exists(all_properties_path):
            logger.info("[%s] loading pre-cached properties", prefix)
            df = pd.read_csv(all_properties_path, sep="\t")
            logger.info("[%s] filtering pre-cached properties", prefix)
            df = df.loc[df["property"] == prop, [f"{prefix}_id", "value"]]
            return dict(df.values)

        logger.info("[%s] no cached properties found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        return ontology.get_filtered_properties_mapping(prop, use_tqdm=use_tqdm)

    return _mapping_getter()


@wrap_norm_prefix
def get_filtered_properties_multimapping(
    prefix: str,
    prop: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    version: Optional[str] = None,
) -> Mapping[str, list[str]]:
    """Extract multiple properties for each term as a dictionary.

    :param prefix: the resource to load
    :param prop: the property to extract
    :param use_tqdm: should a progress bar be shown?
    :param force: should the resource be re-downloaded, re-parsed, and re-cached?
    :returns: A mapping from identifier to property values
    """
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, "properties", name=f"{prop}.tsv", version=version)
    all_properties_path = prefix_cache_join(prefix, name="properties.tsv", version=version)

    @cached_multidict(path=path, header=[f"{prefix}_id", prop], force=force)
    def _mapping_getter() -> Mapping[str, list[str]]:
        if os.path.exists(all_properties_path):
            logger.info("[%s] loading pre-cached properties", prefix)
            df = pd.read_csv(all_properties_path, sep="\t")
            logger.info("[%s] filtering pre-cached properties", prefix)
            df = df.loc[df["property"] == prop, [f"{prefix}_id", "value"]]
            return multidict(df.values)

        logger.info("[%s] no cached properties found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        return ontology.get_filtered_properties_multimapping(prop, use_tqdm=use_tqdm)

    return _mapping_getter()


def get_property(prefix: str, identifier: str, prop: str, **kwargs) -> Optional[str]:
    """Extract a single property for the given entity.

    :param prefix: the resource to load
    :param identifier: the identifier withing the resource
    :param prop: the property to extract
    :returns: The single value for the property. If multiple are expected, use :func:`get_properties`

    >>> import pyobo
    >>> pyobo.get_property("chebi", "132964", "http://purl.obolibrary.org/obo/chebi/smiles")
    "C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F"
    """
    filtered_properties_mapping = get_filtered_properties_mapping(
        prefix=prefix, prop=prop, **kwargs
    )
    return filtered_properties_mapping.get(identifier)


def get_properties(prefix: str, identifier: str, prop: str, **kwargs) -> Optional[list[str]]:
    """Extract a set of properties for the given entity.

    :param prefix: the resource to load
    :param identifier: the identifier withing the resource
    :param prop: the property to extract
    :returns: Multiple values for the property. If only one is expected, use :func:`get_property`
    """
    filtered_properties_multimapping = get_filtered_properties_multimapping(
        prefix=prefix, prop=prop, **kwargs
    )
    return filtered_properties_multimapping.get(identifier)


@wrap_norm_prefix
def get_filtered_properties_df(
    prefix: str,
    prop: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    version: Optional[str] = None,
) -> pd.DataFrame:
    """Extract a single property for each term.

    :param prefix: the resource to load
    :param prop: the property to extract
    :param use_tqdm: should a progress bar be shown?
    :param force: should the resource be re-downloaded, re-parsed, and re-cached?
    :returns: A dataframe from identifier to property value. Columns are [<prefix>_id, value].
    """
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, "properties", name=f"{prop}.tsv", version=version)
    all_properties_path = prefix_cache_join(prefix, name="properties.tsv", version=version)

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if os.path.exists(all_properties_path):
            logger.info("[%s] loading pre-cached properties", prefix)
            df = pd.read_csv(all_properties_path, sep="\t")
            logger.info("[%s] filtering pre-cached properties", prefix)
            return df.loc[df["property"] == prop, [f"{prefix}_id", "value"]]

        if force:
            logger.info("[%s] forcing reload for properties", prefix)
        else:
            logger.info("[%s] no cached properties found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        return ontology.get_filtered_properties_df(prop, use_tqdm=use_tqdm)

    return _df_getter()
