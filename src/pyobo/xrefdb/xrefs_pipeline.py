"""Pipeline for extracting all xrefs from OBO documents available."""

import gzip
import itertools as itt
import logging
from collections.abc import Iterable
from typing import Optional, cast

import bioregistry
import networkx as nx
import pandas as pd
from tqdm.auto import tqdm

from .sources import iter_xref_plugins
from .. import get_xrefs_df
from ..api import (
    get_id_definition_mapping,
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_metadata,
    get_properties_df,
    get_relations_df,
    get_typedef_df,
)
from ..constants import SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX
from ..getters import iter_helper, iter_helper_helper
from ..sources import ncbigene, pubchem
from ..utils.path import ensure_path

logger = logging.getLogger(__name__)


# TODO a normal graph can easily be turned into a directed graph where each
#  edge points from low priority to higher priority, then the graph can
#  be reduced to a set of star graphs and ultimately to a single dictionary


def get_graph_from_xref_df(df: pd.DataFrame) -> nx.Graph:
    """Generate a graph from the mappings dataframe."""
    rv = nx.Graph()

    it = itt.chain(
        df[[SOURCE_PREFIX, SOURCE_ID]].drop_duplicates().values,
        df[[TARGET_PREFIX, TARGET_ID]].drop_duplicates().values,
    )
    it = tqdm(it, desc="loading curies", unit_scale=True)
    for prefix, identifier in it:
        rv.add_node(_to_curie(prefix, identifier), prefix=prefix, identifier=identifier)

    it = tqdm(df.values, total=len(df.index), desc="loading xrefs", unit_scale=True)
    for source_ns, source_id, target_ns, target_id, provenance in it:
        rv.add_edge(
            _to_curie(source_ns, source_id),
            _to_curie(target_ns, target_id),
            provenance=provenance,
        )

    return rv


def _to_curie(prefix: str, identifier: str) -> str:
    return f"{prefix}:{identifier}"


def _iter_ncbigene(left, right):
    ncbi_path = ensure_path(ncbigene.PREFIX, url=ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, "rt") as file:
        next(file)  # throw away the header
        for line in tqdm(
            file, desc=f"extracting {ncbigene.PREFIX}", unit_scale=True, total=27_000_000
        ):
            line = line.strip().split("\t")
            yield ncbigene.PREFIX, line[left], line[right]


def _iter_metadata(**kwargs):
    for prefix, data in iter_helper_helper(get_metadata, **kwargs):
        version = data["version"]
        tqdm.write(f"[{prefix}] using version {version}")
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


def _iter_species(leave: bool = False, **kwargs) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-species triples we can get."""
    yield from iter_helper(get_id_species_mapping, leave=leave, **kwargs)
    # TODO ncbigene


def _iter_definitions(leave: bool = False, **kwargs) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-descriptions triples we can get."""
    yield from iter_helper(get_id_definition_mapping, leave=leave, **kwargs)
    yield from _iter_ncbigene(1, 8)


def _iter_alts(
    leave: bool = False, strict: bool = True, **kwargs
) -> Iterable[tuple[str, str, str]]:
    for prefix, identifier, alts in iter_helper(
        get_id_to_alts, leave=leave, strict=strict, **kwargs
    ):
        for alt in alts:
            yield prefix, identifier, alt


def _iter_synonyms(leave: bool = False, **kwargs) -> Iterable[tuple[str, str, str]]:
    """Iterate over all prefix-identifier-synonym triples we can get.

    :param leave: should the tqdm be left behind?
    """
    for prefix, identifier, synonyms in iter_helper(get_id_synonyms_mapping, leave=leave, **kwargs):
        for synonym in synonyms:
            yield prefix, identifier, synonym


def _iter_typedefs(**kwargs) -> Iterable[tuple[str, str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get."""
    for prefix, df in iter_helper_helper(get_typedef_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str], (prefix, *t))


def _iter_relations(**kwargs) -> Iterable[tuple[str, str, str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_relations_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str, str, str], (prefix, *t))


def _iter_properties(**kwargs) -> Iterable[tuple[str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_properties_df, **kwargs):
        for t in df.values:
            if all(t):
                yield cast(tuple[str, str, str, str], (prefix, *t))


def _iter_xrefs(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
    strict: bool = True,
    **kwargs,
) -> Iterable[tuple[str, str, str, str, str]]:
    it = iter_helper_helper(
        get_xrefs_df,
        use_tqdm=use_tqdm,
        force=force,
        skip_below=skip_below,
        strict=strict,
        **kwargs,
    )
    for prefix, df in it:
        df.dropna(inplace=True)
        for row in df.values:
            if any(not element for element in row):
                continue
            yield cast(tuple[str, str, str, str, str], (prefix, *row, prefix))
    for df in iter_xref_plugins(skip_below=skip_below):
        df.dropna(inplace=True)
        yield from tqdm(df.values, leave=False, total=len(df.index), unit_scale=True)
