"""High-level API for hierarchies."""

import logging
from collections.abc import Iterable
from functools import lru_cache

import networkx as nx
from curies import ReferenceTuple
from typing_extensions import Unpack

from .names import get_name
from .properties import get_filtered_properties_mapping
from .relations import get_relations
from .utils import _get_pi
from ..constants import GetOntologyKwargs
from ..identifier_utils import wrap_norm_prefix
from ..struct import has_member, has_part, is_a, member_of, part_of
from ..struct.reference import Reference
from ..struct.struct_utils import ReferenceHint, _ensure_ref

__all__ = [
    "get_ancestors",
    "get_children",
    "get_descendants",
    "get_hierarchy",
    "get_subhierarchy",
    "has_ancestor",
    "is_descendent",
]

logger = logging.getLogger(__name__)


class HierarchyKwargs(GetOntologyKwargs):
    """Keyword argument hints for hierarchy getter functions."""

    include_part_of: bool
    include_has_member: bool
    use_tqdm: bool


def get_hierarchy(
    prefix: str,
    *,
    extra_relations: Iterable[ReferenceHint] | None = None,
    properties: Iterable[ReferenceHint] | None = None,
    **kwargs: Unpack[HierarchyKwargs],
) -> nx.DiGraph:
    """Get hierarchy of parents as a directed graph.

    :param prefix: The name of the namespace.
    :param include_part_of: Add "part of" relations. Only works if the relations are properly
        defined using bfo:0000050 ! part of or bfo:0000051 ! has part
    :param include_has_member: Add "has member" relations. These aren't part of the BFO, but
        are hacked into PyOBO using :data:`pyobo.struct.typedef.has_member` for relationships like
        from protein families to their actual proteins.
    :param extra_relations: Other relations that you want to include in the hierarchy. For
        example, it might be useful to include the positively_regulates
    :param properties: Properties to include in the data part of each node. For example, might want
        to include SMILES strings with the ChEBI tree.
    :param use_tqdm: Show a progress bar
    :param force: should the resources be reloaded when extracting relations?
    :returns: A directional graph representing the hierarchy

    This function thinly wraps :func:`_get_hierarchy_helper` to make it easier to work with the lru_cache mechanism.
    """
    extra_relations_ = tuple(
        sorted(_ensure_ref(r, ontology_prefix=prefix) for r in extra_relations or [])
    )
    properties_ = tuple(
        sorted(_ensure_ref(prop, ontology_prefix=prefix) for prop in properties or [])
    )
    return _get_hierarchy_helper(
        prefix=prefix, extra_relations=extra_relations_, properties=properties_, **kwargs
    )


@lru_cache
@wrap_norm_prefix
def _get_hierarchy_helper(
    prefix: str,
    *,
    extra_relations: tuple[Reference, ...],
    properties: tuple[Reference, ...],
    include_part_of: bool = False,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> nx.DiGraph:
    predicates = {is_a, *extra_relations}
    reverse_predicates = set()
    if include_part_of:
        predicates.add(part_of)
        reverse_predicates.add(has_part)
    if include_has_member:
        predicates.add(has_member)
        reverse_predicates.add(member_of)

    rv = nx.DiGraph()
    for s, p, o in get_relations(prefix, use_tqdm=use_tqdm, **kwargs):
        if p in predicates:
            rv.add_edge(s.curie, o.curie, relation=p.curie)
        elif p in reverse_predicates:
            rv.add_edge(o.curie, s.curie, relation=p.curie)

    for prop in properties:
        props = get_filtered_properties_mapping(
            prefix=prefix, prop=prop, use_tqdm=use_tqdm, **kwargs
        )
        for identifier, value in props.items():
            curie = f"{prefix}:{identifier}"
            if curie in rv:
                rv.nodes[curie][prop] = value

    return rv


def is_descendent(
    prefix, identifier, ancestor_prefix, ancestor_identifier, *, version: str | None = None
) -> bool:
    """Check that the first identifier has the second as a descendent.

    Check that go:0070246 ! natural killer cell apoptotic process is a
    descendant of go:0006915 ! apoptotic process::
    >>> assert is_descendent("go", "0070246", "go", "0006915")
    """
    descendants = get_descendants(ancestor_prefix, ancestor_identifier, version=version)
    return descendants is not None and f"{prefix}:{identifier}" in descendants


@lru_cache
def get_descendants(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[str] | None:
    """Get all the descendants (children) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t.curie not in hierarchy:
        return None
    return nx.ancestors(hierarchy, t.curie)  # note this is backwards


@lru_cache
def get_children(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[str] | None:
    """Get all the descendants (children) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t.curie not in hierarchy:
        return None
    return set(hierarchy.predecessors(t.curie))


def has_ancestor(
    prefix, identifier, ancestor_prefix, ancestor_identifier, *, version: str | None = None
) -> bool:
    """Check that the first identifier has the second as an ancestor.

    Check that go:0008219 ! cell death is an ancestor of go:0006915 ! apoptotic process::
    >>> assert has_ancestor("go", "0006915", "go", "0008219")
    """
    ancestors = get_ancestors(prefix, identifier, version=version)
    return ancestors is not None and f"{ancestor_prefix}:{ancestor_identifier}" in ancestors


@lru_cache
def get_ancestors(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[str] | None:
    """Get all the ancestors (parents) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t.curie not in hierarchy:
        return None
    return nx.descendants(hierarchy, t.curie)  # note this is backwards


def get_subhierarchy(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> nx.DiGraph:
    """Get the subhierarchy for a given node."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    logger.info("getting descendants of %s:%s ! %s", t.prefix, t.identifier, get_name(t))
    curies = nx.ancestors(hierarchy, t.curie)  # note this is backwards
    logger.info("inducing subgraph")
    sg = hierarchy.subgraph(curies).copy()
    logger.info("subgraph has %d nodes/%d edges", sg.number_of_nodes(), sg.number_of_edges())
    return sg
