# -*- coding: utf-8 -*-

"""Pipeline for building a large ontology graph."""

import logging

import bioregistry
import networkx as nx
from tqdm import tqdm

from pyobo import get_hierarchy
from pyobo.getters import SKIP
from pyobo.resource_utils import ensure_inspector_javert_df

logger = logging.getLogger(__name__)


def bens_magical_ontology(use_tqdm: bool = True) -> nx.DiGraph:
    """Make a super graph containing is_a, part_of, and xref relationships."""
    rv = nx.DiGraph()

    df = ensure_inspector_javert_df()
    for source_ns, source_id, target_ns, target_id, provenance in df.values:
        rv.add_edge(
            f"{source_ns}:{source_id}",
            f"{target_ns}:{target_id}",
            relation="xref",
            provenance=provenance,
        )

    logger.info("getting hierarchies")
    it = sorted(bioregistry.read_registry())
    if use_tqdm:
        it = tqdm(it, desc="Entries")
    for prefix in it:
        if bioregistry.is_deprecated(prefix) or prefix in SKIP:
            continue
        if use_tqdm:
            it.set_postfix({"prefix": prefix})

        hierarchy = get_hierarchy(prefix, include_has_member=True, include_part_of=True)
        rv.add_edges_from(hierarchy.edges(data=True))

    # TODO include translates_to, transcribes_to, and has_variant

    return rv
