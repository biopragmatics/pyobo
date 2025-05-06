"""High-level API for edges."""

import networkx as nx
import pandas as pd
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api.names import get_ids
from pyobo.api.utils import get_version_from_kwargs
from pyobo.constants import (
    GetOntologyKwargs,
    check_should_cache,
    check_should_force,
    check_should_use_tqdm,
)
from pyobo.getters import get_ontology

from ..struct import Reference
from ..utils.cache import cached_df
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_edges",
    "get_edges_df",
    "get_graph",
]


def get_graph(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> nx.DiGraph:
    """Get the relation graph."""
    rv = nx.MultiDiGraph()
    for s in get_ids(prefix, **kwargs):
        rv.add_node(f"{prefix}:{s}")
    df = get_edges_df(prefix=prefix, **kwargs)
    for s, p, o in df.values:
        rv.add_edge(s, p, key=o)
    return rv


def get_edges_df(prefix, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get a dataframe of edges triples."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.edges, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        return get_ontology(prefix, **kwargs).get_edges_df(use_tqdm=check_should_use_tqdm(kwargs))

    return _df_getter()


def get_edges(
    prefix, **kwargs: Unpack[GetOntologyKwargs]
) -> list[tuple[Reference, Reference, Reference]]:
    """Get a list of edge triples."""
    df = get_edges_df(prefix, **kwargs)
    return [
        (Reference.from_curie(s), Reference.from_curie(p), Reference.from_curie(o))
        for s, p, o in tqdm(
            df.values,
            desc=f"[{prefix}] parsing edges",
            unit="edge",
            unit_scale=True,
            disable=not check_should_use_tqdm(kwargs),
        )
    ]
