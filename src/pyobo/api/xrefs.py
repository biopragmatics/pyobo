"""High-level API for synonyms."""

import logging
import warnings
from collections.abc import Mapping
from functools import lru_cache

import pandas as pd
from curies import ReferenceTuple
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import (
    TARGET_ID,
    TARGET_PREFIX,
    GetOntologyKwargs,
    check_should_cache,
    check_should_force,
    check_should_use_tqdm,
)
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct import Obo
from ..utils.cache import cached_df
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_filtered_xrefs",
    "get_mappings_df",
    "get_sssom_df",
    "get_xref",
    "get_xrefs",
    "get_xrefs_df",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_xref(
    prefix: str,
    identifier: str,
    new_prefix: str,
    *,
    flip: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the xref with the new prefix if a direct path exists."""
    filtered_xrefs = get_filtered_xrefs(prefix, new_prefix, flip=flip, **kwargs)
    return filtered_xrefs.get(identifier)


@lru_cache
@wrap_norm_prefix
def get_filtered_xrefs(
    prefix: str,
    xref_prefix: str,
    *,
    flip: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    mappings_df = get_mappings_df(prefix, **kwargs)

    rv = {}
    for subject_curie, object_curie in mappings_df[["subject_id", "object_id"]].values:
        subject_pair = ReferenceTuple.from_curie(subject_curie)
        object_pair = ReferenceTuple.from_curie(object_curie)
        if object_pair.prefix == xref_prefix:
            rv[subject_pair.identifier] = object_pair.identifier

    if flip:
        return {v: k for k, v in rv.items()}
    return rv


get_xrefs = get_filtered_xrefs


@wrap_norm_prefix
def get_xrefs_df(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get all xrefs."""
    warnings.warn(
        "use pyobo.get_mappings_df instead of pyobo.get_xrefs_df.",
        DeprecationWarning,
        stacklevel=2,
    )

    mappings_df = get_mappings_df(prefix, **kwargs)

    rows = []
    for subject_curie, object_curie in mappings_df[["subject_id", "object_id"]].values:
        subject_pair = ReferenceTuple.from_curie(subject_curie)
        object_pair = ReferenceTuple.from_curie(object_curie)
        rows.append((subject_pair.identifier, object_pair.prefix, object_pair.identifier))

    df = pd.DataFrame(rows, columns=[f"{prefix}_id", TARGET_PREFIX, TARGET_ID])
    df = df.drop_duplicates()
    return df


def get_sssom_df(
    prefix: str | Obo, *, names: bool = True, **kwargs: Unpack[GetOntologyKwargs]
) -> pd.DataFrame:
    """Get an SSSOM dataframe, replaced by :func:`get_mappings_df`."""
    warnings.warn("get_sssom_df was renamed to get_mappings_df", DeprecationWarning, stacklevel=2)
    return get_mappings_df(prefix=prefix, names=names, **kwargs)


def get_mappings_df(
    prefix: str | Obo,
    *,
    names: bool = True,
    include_mapping_source_column: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    r"""Get semantic mappings from a source as an SSSOM dataframe.

    :param prefix: The ontology to look in for xrefs
    :param names: Add name columns (``subject_label`` and ``object_label``)

    :returns: A SSSOM-compliant dataframe of xrefs

    For example, if you want to get UMLS as an SSSOM dataframe, you can do

    .. code-block:: python

        import pyobo

        df = pyobo.get_mappings_df("umls")
        df.to_csv("umls.sssom.tsv", sep="\t", index=False)

    If you don't want to get all of the many resources required to add names, you can
    pass ``names=False``

    .. code-block:: python

        import pyobo

        df = pyobo.get_mappings_df("umls", names=False)
        df.to_csv("umls.sssom.tsv", sep="\t", index=False)

    .. note::

        This assumes the Bioregistry as the prefix map
    """
    if isinstance(prefix, Obo):
        df = prefix.get_mappings_df(
            include_subject_labels=names,
            include_mapping_source_column=include_mapping_source_column,
            use_tqdm=check_should_use_tqdm(kwargs),
        )
        prefix = prefix.ontology

    else:
        version = get_version_from_kwargs(prefix, kwargs)
        path = get_cache_path(prefix, CacheArtifact.mappings, version=version)

        @cached_df(
            path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
        )
        def _df_getter() -> pd.DataFrame:
            logger.info("[%s] rebuilding SSSOM", prefix)
            ontology = get_ontology(prefix, **kwargs)
            return ontology.get_mappings_df(
                use_tqdm=check_should_use_tqdm(kwargs),
                include_subject_labels=True,
                include_mapping_source_column=include_mapping_source_column,
            )

        df = _df_getter()

    if names:
        from .names import get_name_by_curie

        df["object_label"] = df["object_id"].map(get_name_by_curie)
    elif "subject_label" in df.columns:
        del df["subject_label"]

    return df
