"""High-level API for hierarchies."""

import logging
from collections.abc import Iterable
from functools import lru_cache
from typing import Optional

import networkx as nx

from .names import get_name
from .properties import get_filtered_properties_mapping
from .relations import get_filtered_relations_df
from ..identifier_utils import wrap_norm_prefix
from ..struct import TypeDef, has_member, is_a, part_of
from ..struct.reference import Reference

__all__ = [
    "get_hierarchy",
    "get_subhierarchy",
    "get_descendants",
    "get_ancestors",
    "has_ancestor",
    "is_descendent",
    "get_children",
]


logger = logging.getLogger(__name__)


def get_hierarchy(
    prefix: str,
    *,
    include_part_of: bool = True,
    include_has_member: bool = False,
    extra_relations: Optional[Iterable[TypeDef]] = None,
    properties: Optional[Iterable[str]] = None,
    use_tqdm: bool = False,
    force: bool = False,
    version: Optional[str] = None,
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
    return _get_hierarchy_helper(
        prefix=prefix,
        include_part_of=include_part_of,
        include_has_member=include_has_member,
        extra_relations=tuple(sorted(extra_relations or [], key=lambda t: t.curie)),
        properties=tuple(sorted(properties or [])),
        use_tqdm=use_tqdm,
        force=force,
        version=version,
    )


@lru_cache
@wrap_norm_prefix
def _get_hierarchy_helper(
    prefix: str,
    *,
    extra_relations: tuple[TypeDef, ...],
    properties: tuple[str, ...],
    include_part_of: bool,
    include_has_member: bool,
    use_tqdm: bool,
    force: bool = False,
    version: Optional[str] = None,
) -> nx.DiGraph:
    rv = nx.DiGraph()

    is_a_df = get_filtered_relations_df(
        prefix=prefix,
        relation=is_a,
        use_tqdm=use_tqdm,
        force=force,
        version=version,
    )
    for source_id, target_ns, target_id in is_a_df.values:
        rv.add_edge(f"{prefix}:{source_id}", f"{target_ns}:{target_id}", relation="is_a")

    if include_has_member:
        has_member_df = get_filtered_relations_df(
            prefix=prefix,
            relation=has_member,
            use_tqdm=use_tqdm,
            force=force,
            version=version,
        )
        for target_id, source_ns, source_id in has_member_df.values:
            rv.add_edge(f"{source_ns}:{source_id}", f"{prefix}:{target_id}", relation="is_a")

    if include_part_of:
        part_of_df = get_filtered_relations_df(
            prefix=prefix,
            relation=part_of,
            use_tqdm=use_tqdm,
            force=force,
            version=version,
        )
        for source_id, target_ns, target_id in part_of_df.values:
            rv.add_edge(f"{prefix}:{source_id}", f"{target_ns}:{target_id}", relation="part_of")

        has_part_df = get_filtered_relations_df(
            prefix=prefix,
            relation=part_of,
            use_tqdm=use_tqdm,
            force=force,
            version=version,
        )
        for target_id, source_ns, source_id in has_part_df.values:
            rv.add_edge(f"{source_ns}:{source_id}", f"{prefix}:{target_id}", relation="part_of")

    for relation in extra_relations:
        if not isinstance(relation, (TypeDef, Reference)):
            raise TypeError
        relation_df = get_filtered_relations_df(
            prefix=prefix,
            relation=relation,
            use_tqdm=use_tqdm,
            force=force,
            version=version,
        )
        for source_id, target_ns, target_id in relation_df.values:
            rv.add_edge(
                f"{prefix}:{source_id}", f"{target_ns}:{target_id}", relation=relation.identifier
            )

    for prop in properties:
        props = get_filtered_properties_mapping(
            prefix=prefix, prop=prop, use_tqdm=use_tqdm, force=force
        )
        for identifier, value in props.items():
            curie = f"{prefix}:{identifier}"
            if curie in rv:
                rv.nodes[curie][prop] = value

    return rv


def is_descendent(
    prefix, identifier, ancestor_prefix, ancestor_identifier, *, version: Optional[str] = None
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
    prefix: str,
    identifier: Optional[str] = None,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Optional[set[str]]:
    """Get all the descendants (children) of the term as CURIEs."""
    curie, prefix, identifier = _pic(prefix, identifier)
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    if curie not in hierarchy:
        return None
    return nx.ancestors(hierarchy, curie)  # note this is backwards


def _pic(prefix, identifier=None) -> tuple[str, str, str]:
    if identifier is None:
        curie = prefix
        prefix, identifier = prefix.split(":")
    else:
        curie = f"{prefix}:{identifier}"
    return curie, prefix, identifier


@lru_cache
def get_children(
    prefix: str,
    identifier: Optional[str] = None,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Optional[set[str]]:
    """Get all the descendants (children) of the term as CURIEs."""
    curie, prefix, identifier = _pic(prefix, identifier)
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    if curie not in hierarchy:
        return None
    return set(hierarchy.predecessors(curie))


def has_ancestor(
    prefix, identifier, ancestor_prefix, ancestor_identifier, *, version: Optional[str] = None
) -> bool:
    """Check that the first identifier has the second as an ancestor.

    Check that go:0008219 ! cell death is an ancestor of go:0006915 ! apoptotic process::
    >>> assert has_ancestor("go", "0006915", "go", "0008219")
    """
    ancestors = get_ancestors(prefix, identifier, version=version)
    return ancestors is not None and f"{ancestor_prefix}:{ancestor_identifier}" in ancestors


@lru_cache
def get_ancestors(
    prefix: str,
    identifier: Optional[str] = None,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Optional[set[str]]:
    """Get all the ancestors (parents) of the term as CURIEs."""
    curie, prefix, identifier = _pic(prefix, identifier)
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    if curie not in hierarchy:
        return None
    return nx.descendants(hierarchy, curie)  # note this is backwards


def get_subhierarchy(
    prefix: str,
    identifier: Optional[str] = None,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> nx.DiGraph:
    """Get the subhierarchy for a given node."""
    curie, prefix, identifier = _pic(prefix, identifier)
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    logger.info(
        "getting descendants of %s:%s ! %s", prefix, identifier, get_name(prefix, identifier)
    )
    curies = nx.ancestors(hierarchy, curie)  # note this is backwards
    logger.info("inducing subgraph")
    sg = hierarchy.subgraph(curies).copy()
    logger.info("subgraph has %d nodes/%d edges", sg.number_of_nodes(), sg.number_of_edges())
    return sg
