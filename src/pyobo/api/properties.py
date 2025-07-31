"""High-level API for properties."""

import logging
from collections.abc import Mapping

import pandas as pd
from tqdm import tqdm
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import (
    GetOntologyKwargs,
    check_should_cache,
    check_should_force,
    check_should_use_tqdm,
)
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct import Reference
from ..struct.struct_utils import OBOLiteral, ReferenceHint, _ensure_ref
from ..utils.cache import cached_df
from ..utils.io import multidict
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_filtered_properties_df",
    "get_filtered_properties_mapping",
    "get_filtered_properties_multimapping",
    "get_literal_properties",
    "get_literal_properties_df",
    "get_object_properties",
    "get_object_properties_df",
    "get_properties",
    "get_properties_df",
    "get_property",
]

logger = logging.getLogger(__name__)


def get_object_properties_df(prefix, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get a dataframe of object property triples."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.object_properties, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        return get_ontology(prefix, **kwargs).get_object_properties_df(
            use_tqdm=check_should_use_tqdm(kwargs)
        )

    return _df_getter()


def get_object_properties(
    prefix, **kwargs: Unpack[GetOntologyKwargs]
) -> list[tuple[Reference, Reference, Reference]]:
    """Get a list of object property triples."""
    df = get_object_properties_df(prefix, **kwargs)
    return [
        (Reference.from_curie(s), Reference.from_curie(p), Reference.from_curie(o))
        for s, p, o in df.values
    ]


def get_literal_properties(
    prefix: str, **kwargs: Unpack[GetOntologyKwargs]
) -> list[tuple[Reference, Reference, OBOLiteral]]:
    """Get a list of literal property triples."""
    df = get_literal_properties_df(prefix, **kwargs)
    return [
        (
            Reference.from_curie(s),
            Reference.from_curie(p),
            OBOLiteral(
                value,
                Reference.from_curie(datatype),
                language if language and pd.notna(language) else None,
            ),
        )
        for s, p, value, datatype, language in tqdm(
            df.values,
            desc=f"[{prefix}] parsing properties",
            unit_scale=True,
            unit="triple",
            disable=not check_should_use_tqdm(kwargs),
        )
    ]


def get_literal_properties_df(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get a dataframe of literal property quads."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.literal_properties, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        return get_ontology(prefix, **kwargs).get_literal_properties_df(
            use_tqdm=check_should_use_tqdm(kwargs)
        )

    return _df_getter()


@wrap_norm_prefix
def get_properties_df(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Extract properties.

    :param prefix: the resource to load
    :returns: A dataframe with the properties
    """
    df1 = get_literal_properties_df(prefix, **kwargs)
    df2 = get_object_properties_df(prefix, **kwargs)
    df = pd.concat([df1[["source", "predicate", "target"]], df2])
    ll = len(prefix) + 1
    df[f"{prefix}_id"] = df["source"].map(lambda x: x[ll:])
    df = df.rename(columns={"predicate": "property", "target": "value"})
    del df["source"]
    return df[[f"{prefix}_id", "property", "value"]]


@wrap_norm_prefix
def get_filtered_properties_mapping(
    prefix: str, prop: ReferenceHint, **kwargs: Unpack[GetOntologyKwargs]
) -> Mapping[str, str]:
    """Extract a single property for each term as a dictionary.

    :param prefix: the resource to load
    :param prop: the property to extract
    :returns: A mapping from identifier to property value
    """
    df = get_filtered_properties_df(prefix, prop, **kwargs)
    return dict(df.values)


@wrap_norm_prefix
def get_filtered_properties_multimapping(
    prefix: str, prop: ReferenceHint, **kwargs: Unpack[GetOntologyKwargs]
) -> Mapping[str, list[str]]:
    """Extract multiple properties for each term as a dictionary.

    :param prefix: the resource to load
    :param prop: the property to extract
    :returns: A mapping from identifier to property values
    """
    df = get_filtered_properties_df(prefix, prop, **kwargs)
    return multidict(df.values)


def get_property(
    prefix: str, identifier: str, prop: ReferenceHint, **kwargs: Unpack[GetOntologyKwargs]
) -> str | None:
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


def get_properties(
    prefix: str,
    identifier: str,
    prop: ReferenceHint,
    **kwargs: Unpack[GetOntologyKwargs],
) -> list[str] | None:
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
    prefix: str, prop: ReferenceHint, **kwargs: Unpack[GetOntologyKwargs]
) -> pd.DataFrame:
    """Extract a single property for each term.

    :param prefix: the resource to load
    :param prop: the property to extract
    :returns: A dataframe from identifier to property value. Columns are [<prefix>_id, value].
    """
    prop = _ensure_ref(prop, ontology_prefix=prefix)
    df = get_properties_df(prefix, **kwargs)
    df = df.loc[df["property"] == prop.curie, [f"{prefix}_id", "value"]]
    return df
