"""Pipeline for extracting all xrefs from OBO documents available."""

from __future__ import annotations

import functools
import gzip
import logging
import warnings
from collections.abc import Iterable
from functools import partial
from typing import cast

import bioregistry
from tqdm.auto import tqdm
from typing_extensions import Unpack

from ..api import (
    get_edges_df,
    get_id_definition_mapping,
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_mappings_df,
    get_metadata,
    get_prefixes,
    get_properties_df,
    get_relations_df,
    get_typedef_df,
    get_xrefs_df,
)
from ..api.metadata import get_references_to
from ..getters import IterHelperHelperDict, iter_helper, iter_helper_helper
from ..sources import pubchem
from ..sources.ncbi import ncbigene
from ..utils.path import ensure_path
from ..xrefdb.sources import iter_xref_plugins

logger = logging.getLogger(__name__)


def _iter_ncbigene(left: int, right: int) -> Iterable[tuple[str, str, str]]:
    ncbi_path = ensure_path(ncbigene.PREFIX, url=ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, "rt") as file:
        next(file)  # throw away the header
        for line in tqdm(
            file, desc=f"extracting {ncbigene.PREFIX}", unit_scale=True, total=27_000_000
        ):
            line = line.strip().split("\t")
            yield ncbigene.PREFIX, line[left], line[right]


def _iter_metadata(**kwargs: Unpack[IterHelperHelperDict]):
    for prefix, data in iter_helper_helper(get_metadata, **kwargs):
        version = data["version"]
        logger.debug(f"[{prefix}] using version {version}")
        yield prefix, version, data["date"], bioregistry.is_deprecated(prefix)


def _iter_names(leave: bool = False, **kwargs) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get.

    :param leave: should the tqdm be left behind?
    """
    yield from iter_helper(get_id_name_mapping, leave=leave, **kwargs)
    yield from _iter_ncbigene(1, 2)

    pcc_path = pubchem._ensure_cid_name_path()
    with gzip.open(pcc_path, mode="rt", encoding="ISO-8859-1") as file:
        for line in tqdm(
            file, desc=f"extracting {pubchem.PREFIX}", unit_scale=True, total=103_000_000
        ):
            identifier, name = line.strip().split("\t", 1)
            yield pubchem.PREFIX, identifier, name


def _iter_species(
    leave: bool = False, **kwargs: Unpack[IterHelperHelperDict]
) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-species triples we can get."""
    yield from iter_helper(get_id_species_mapping, leave=leave, **kwargs)
    # TODO ncbigene


def _iter_definitions(
    leave: bool = False, **kwargs: Unpack[IterHelperHelperDict]
) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-descriptions triples we can get."""
    yield from iter_helper(get_id_definition_mapping, leave=leave, **kwargs)
    yield from _iter_ncbigene(1, 8)


def _iter_alts(
    leave: bool = False, **kwargs: Unpack[IterHelperHelperDict]
) -> Iterable[tuple[str, str, str]]:
    for prefix, identifier, alts in iter_helper(get_id_to_alts, leave=leave, **kwargs):
        for alt in alts:
            yield prefix, identifier, alt


def _iter_synonyms(
    leave: bool = False, **kwargs: Unpack[IterHelperHelperDict]
) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-synonym triples we can get.

    :param leave: should the tqdm be left behind?
    """
    for prefix, identifier, synonyms in iter_helper(get_id_synonyms_mapping, leave=leave, **kwargs):
        for synonym in synonyms:
            yield prefix, identifier, synonym


def _iter_typedefs(**kwargs: Unpack[IterHelperHelperDict]) -> Iterable[tuple[str, str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get."""
    for prefix, df in iter_helper_helper(get_typedef_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str], (prefix, *t))


def _iter_relations(
    **kwargs: Unpack[IterHelperHelperDict],
) -> Iterable[tuple[str, str, str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_relations_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str, str, str], (prefix, *t))


def _iter_edges(**kwargs: Unpack[IterHelperHelperDict]) -> Iterable[tuple[str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_edges_df, **kwargs):
        for row in df.values:
            yield cast(tuple[str, str, str, str], (*row, prefix))


def _iter_properties(**kwargs: Unpack[IterHelperHelperDict]) -> Iterable[tuple[str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_properties_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str], (prefix, *t))


def _iter_xrefs(
    **kwargs: Unpack[IterHelperHelperDict],
) -> Iterable[tuple[str, str, str, str, str]]:
    warnings.warn(f"use {_iter_mappings.__name__} instead", DeprecationWarning, stacklevel=2)
    it = iter_helper_helper(get_xrefs_df, **kwargs)
    for prefix, df in it:
        df.dropna(inplace=True)
        for row in df.values:
            if any(not element for element in row):
                continue
            yield cast(tuple[str, str, str, str, str], (prefix, *row, prefix))
    for df in iter_xref_plugins(skip_below=kwargs.get("skip_below")):
        df.dropna(inplace=True)
        yield from tqdm(df.values, leave=False, total=len(df.index), unit_scale=True)


def _iter_mappings(
    **kwargs: Unpack[IterHelperHelperDict],
) -> Iterable[tuple[str, str, str, str, str]]:
    f = partial(get_mappings_df, names=False, include_mapping_source_column=True)
    # hack in a name to the partial function object since
    # it's used for the tqdm description in iter_helper_helper
    f.__name__ = "get_mappings_df"  # type:ignore
    it = iter_helper_helper(f, **kwargs)
    for _prefix, df in it:
        yield from df.values


def _iter_prefix_count(**kwargs: Unpack[IterHelperHelperDict]) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-external prefix-count triples.

    :param leave: should the tqdm be left behind?
    """
    for prefix, external_prefix, count in iter_helper(get_prefixes, **kwargs):
        if prefix != external_prefix:
            yield prefix, external_prefix, str(count)


def _iter_ec(ext: str, **kwargs: Unpack[IterHelperHelperDict]) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-ec pairs.

    :param leave: should the tqdm be left behind?
    """
    f = functools.partial(get_references_to, ext=ext)
    f.__name__ = "get_references_to_"  # type:ignore
    for prefix, ext, count in iter_helper(f, **kwargs):
        yield prefix, ext, str(count)
