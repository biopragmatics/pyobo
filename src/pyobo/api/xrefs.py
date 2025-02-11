"""High-level API for synonyms."""

import logging
import warnings
from collections.abc import Mapping
from functools import lru_cache

import pandas as pd
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import (
    BUILD_SUBDIRECTORY_NAME,
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
from ..utils.cache import cached_df, cached_mapping
from ..utils.path import prefix_cache_join, prefix_directory_join

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
    version = get_version_from_kwargs(prefix, kwargs)
    path = prefix_cache_join(prefix, "xrefs", name=f"{xref_prefix}.tsv", version=version)
    all_xrefs_path = prefix_cache_join(prefix, name="xrefs.tsv", version=version)
    header = [f"{prefix}_id", f"{xref_prefix}_id"]

    @cached_mapping(
        path=path,
        header=header,
        use_tqdm=check_should_use_tqdm(kwargs),
        force=check_should_force(kwargs),
        cache=check_should_cache(kwargs),
    )
    def _get_mapping() -> Mapping[str, str]:
        if all_xrefs_path.is_file():
            logger.info("[%s] loading pre-cached xrefs", prefix)
            df = pd.read_csv(all_xrefs_path, sep="\t", dtype=str)
            logger.info("[%s] filtering pre-cached xrefs", prefix)
            df = df.loc[df[TARGET_PREFIX] == xref_prefix, [f"{prefix}_id", TARGET_ID]]
            return dict(df.values)

        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_filtered_xrefs_mapping(
            xref_prefix, use_tqdm=check_should_use_tqdm(kwargs)
        )

    rv = _get_mapping()
    if flip:
        return {v: k for k, v in rv.items()}
    return rv


get_xrefs = get_filtered_xrefs


@wrap_norm_prefix
def get_xrefs_df(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get all xrefs."""
    warnings.warn(
        "use pyobo.get_mappings_df instead of pyobo.get_xrefs_df", DeprecationWarning, stacklevel=2
    )

    version = get_version_from_kwargs(prefix, kwargs)
    path = prefix_cache_join(prefix, name="xrefs.tsv", version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_xrefs_df(use_tqdm=check_should_use_tqdm(kwargs))

    return _df_getter()


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
        path = prefix_directory_join(
            prefix, BUILD_SUBDIRECTORY_NAME, name="sssom.tsv", version=version
        )

        @cached_df(
            path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
        )
        def _df_getter() -> pd.DataFrame:
            logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
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
