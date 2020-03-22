# -*- coding: utf-8 -*-

"""Utilities for extracting synonyms."""

import logging
from typing import Iterable, List, Mapping, Tuple, Union

import networkx as nx
import pandas as pd

from ..getters import get_obo_graph
from ..graph_utils import iterate_obo_nodes
from ..io_utils import multidict
from ..struct import Reference, TypeDef

__all__ = [
    'get_relations_df',
    'get_id_to_relations',
]

logger = logging.getLogger(__name__)


def get_relations_df(prefix: str, **kwargs) -> pd.DataFrame:
    """Get all relations from the OBO."""
    graph = get_obo_graph(prefix, **kwargs)
    return pd.DataFrame(
        _iterate_relations(graph=graph, prefix=prefix),
        columns=[f'{prefix}_id', 'relation_ns', 'relation_id', 'target_ns', 'target_id'],
    )


def get_id_to_relations(prefix: str, target_relation: Union[str, TypeDef], **kwargs) -> Mapping[str, List[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    # path = prefix_directory_join(prefix, f"{prefix}_relations.tsv")
    # header = [f'{prefix}_id', 'relation']
    graph = get_obo_graph(prefix, **kwargs)
    rv = multidict(_iterate(graph=graph, prefix=prefix, target_relation=target_relation))
    return rv


def _iterate(
    *,
    graph: nx.MultiDiGraph,
    prefix: str,
    target_relation: TypeDef,
) -> Iterable[Tuple[str, Reference]]:
    for identifier, relation_ns, relation_id, target_ns, target_id in _iterate_relations(graph=graph, prefix=prefix):
        if relation_ns == target_relation.prefix and relation_id == target_relation.identifier:
            yield identifier, Reference(prefix=target_ns, identifier=target_id)


def get_typedefs(*, graph: nx.MultiDiGraph, prefix: str) -> Iterable[TypeDef]:
    """Get type defs from the graph."""
    for typedef in graph.graph.get('typedefs', []):
        identifier, name = typedef['id'], typedef['name']
        xrefs = [
            Reference.from_curie(curie)
            for curie in typedef.get('xref', [])
        ]
        yield TypeDef(
            reference=Reference(prefix=prefix, identifier=identifier, name=name),
            xrefs=xrefs,
        )


def _iterate_relations(*, graph: nx.MultiDiGraph, prefix: str) -> Iterable[Tuple[str, str, str, str, str]]:
    typedefs = {
        typedef.identifier: typedef
        for typedef in get_typedefs(graph=graph, prefix=prefix)
    }

    for identifier, data in iterate_obo_nodes(graph=graph, prefix=prefix, skip_external=True):
        for parent in data.get('is_a', []):
            parent = Reference.from_curie(parent)
            yield identifier, 'pyobo', 'is_a', parent.prefix, parent.identifier

        for relation in data.get('relationship', []):
            relation_curie, target_curie = relation.split(' ')
            target = Reference.from_curie(target_curie)

            if relation_curie in typedefs:
                relation = typedefs[relation_curie]
            # elif relation_curie in COMMON_RELATIONS:
            #     relation = COMMON_RELATIONS[relation_curie]
            else:
                try:
                    relation = Reference.from_curie(relation_curie)
                except ValueError:  # not enough values to unpack
                    logger.warning(f'unhandled relation: {relation_curie}')

            yield identifier, relation.prefix, relation.identifier, target.prefix, target.identifier
