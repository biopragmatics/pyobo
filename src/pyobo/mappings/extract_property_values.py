# -*- coding: utf-8 -*-

"""Extract relations."""

import datetime
import logging
from typing import Iterable, Optional, Tuple

import networkx as nx
import pandas as pd

from ..getters import get_obo_graph
from ..graph_utils import iterate_obo_nodes

__all__ = [
    'get_properties_df',
    'iterate_properties',
]

logger = logging.getLogger(__name__)

HANDLED_TYPES = {
    'xsd:string': str,
    'xsd:dateTime': datetime.datetime,
}


def get_properties_df(prefix: str, property_prefix: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """Extract ChEBI SMILES."""
    graph = get_obo_graph(prefix, **kwargs)
    return pd.DataFrame(
        iterate_properties(graph=graph, prefix=prefix, property_prefix=property_prefix),
        columns=[f'{prefix}_id', 'property', 'value'],
    )


def iterate_properties(
    *,
    graph: nx.MultiDiGraph,
    prefix: str,
    property_prefix: Optional[str] = None,
) -> Iterable[Tuple[str, str, str]]:
    """Iterate over the properties for each node in the graph."""
    for identifier, data in iterate_obo_nodes(graph=graph, prefix=prefix):
        for prop_value_type in data.get('property_value', []):
            prop, value_type = prop_value_type.split(' ', 1)
            if property_prefix is not None and prop.startswith(property_prefix):
                prop = prop[len(property_prefix):]

            try:
                value, _ = value_type.rsplit(' ', 1)  # second entry is the value type
            except ValueError:
                logger.warning(f'problem with {prefix} - {prop_value_type}')
                value = value_type  # could assign type to be 'xsd:string' by default
            value = value.strip('"')
            yield identifier, prop, value
