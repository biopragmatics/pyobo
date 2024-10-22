"""High-level API for synonyms."""

import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Optional, Union

import pandas as pd
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .utils import get_version
from ..constants import TARGET_ID, TARGET_PREFIX
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct import Obo, Reference
from ..utils.cache import cached_df, cached_mapping
from ..utils.path import prefix_cache_join

__all__ = [
    "get_xrefs_df",
    "get_filtered_xrefs",
    "get_xref",
    "get_xrefs",
    "get_sssom_df",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_xref(
    prefix: str,
    identifier: str,
    new_prefix: str,
    *,
    flip: bool = False,
    version: Optional[str] = None,
) -> Optional[str]:
    """Get the xref with the new prefix if a direct path exists."""
    filtered_xrefs = get_filtered_xrefs(prefix, new_prefix, flip=flip, version=version)
    return filtered_xrefs.get(identifier)


@lru_cache
@wrap_norm_prefix
def get_filtered_xrefs(
    prefix: str,
    xref_prefix: str,
    *,
    flip: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    strict: bool = False,
    version: Optional[str] = None,
) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, "xrefs", name=f"{xref_prefix}.tsv", version=version)
    all_xrefs_path = prefix_cache_join(prefix, name="xrefs.tsv", version=version)
    header = [f"{prefix}_id", f"{xref_prefix}_id"]

    @cached_mapping(path=path, header=header, use_tqdm=use_tqdm, force=force)
    def _get_mapping() -> Mapping[str, str]:
        if all_xrefs_path.is_file():
            logger.info("[%s] loading pre-cached xrefs", prefix)
            df = pd.read_csv(all_xrefs_path, sep="\t", dtype=str)
            logger.info("[%s] filtering pre-cached xrefs", prefix)
            df = df.loc[df[TARGET_PREFIX] == xref_prefix, [f"{prefix}_id", TARGET_ID]]
            return dict(df.values)

        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_filtered_xrefs_mapping(xref_prefix, use_tqdm=use_tqdm)

    rv = _get_mapping()
    if flip:
        return {v: k for k, v in rv.items()}
    return rv


get_xrefs = get_filtered_xrefs


@wrap_norm_prefix
def get_xrefs_df(
    prefix: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    strict: bool = False,
    version: Optional[str] = None,
) -> pd.DataFrame:
    """Get all xrefs."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="xrefs.tsv", version=version)

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_xrefs_df(use_tqdm=use_tqdm)

    return _df_getter()


def get_sssom_df(
    prefix: Union[str, Obo],
    *,
    predicate_id: str = "oboinowl:hasDbXref",
    justification: str = "sempav:UnspecifiedMatching",
    names: bool = True,
    **kwargs,
) -> pd.DataFrame:
    r"""Get xrefs from a source as an SSSOM dataframe.

    :param prefix: The ontology to look in for xrefs
    :param predicate_id: The predicate used in the SSSOM document. By default, ontologies
        don't typically ascribe semantics to xrefs so ``oboinowl:hasDbXref`` is used
    :param justification: The justification for the mapping. By default, ontologies
        don't typically ascribe semantics, so this is left with `sempav:UnspecifiedMatching`
    :param names: Add name columns (``subject_label`` and ``object_label``)
    :returns: A SSSOM-compliant dataframe of xrefs

    For example, if you want to get UMLS as an SSSOM dataframe, you can do

    >>> import pyobo
    >>> df = pyobo.get_sssom_df("umls")
    >>> df.to_csv("umls.sssom.tsv", sep="\t", index=False)

    If you don't want to get all of the many resources required to add
    names, you can pass ``names=False``

    >>> import pyobo
    >>> df = pyobo.get_sssom_df("umls", names=False)
    >>> df.to_csv("umls.sssom.tsv", sep="\t", index=False)

    .. note:: This assumes the Bioregistry as the prefix map
    """
    from .names import get_name

    if isinstance(prefix, Obo):
        df = prefix.get_xrefs_df()
        prefix = prefix.ontology
    else:
        df = get_xrefs_df(prefix=prefix, **kwargs)
    rows: list[tuple[str, ...]] = []
    with logging_redirect_tqdm():
        for source_id, target_prefix, target_id in tqdm(
            df.values, unit="mapping", unit_scale=True, desc=f"[{prefix}] SSSOM"
        ):
            source = Reference(prefix=prefix, identifier=source_id)
            target = Reference(prefix=target_prefix, identifier=target_id)

            if names:
                rows.append(
                    (
                        source.curie,
                        get_name(prefix, source_id) or "",
                        target.curie,
                        get_name(target_prefix, target_id),
                        predicate_id,
                        justification,
                    )
                )
            else:
                rows.append((source.curie, target.curie, predicate_id, justification))

    if names:
        columns = [
            "subject_id",
            "subject_label",
            "object_id",
            "object_label",
            "predicate_id",
            "mapping_justification",
        ]
    else:
        columns = [
            "subject_id",
            "object_id",
            "predicate_id",
            "mapping_justification",
        ]
    return pd.DataFrame(rows, columns=columns)
