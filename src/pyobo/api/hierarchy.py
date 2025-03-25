"""High-level API for hierarchies."""

import logging
import warnings
from collections.abc import Iterable
from functools import lru_cache
from typing import overload

import networkx as nx
from curies import ReferenceTuple
from typing_extensions import NotRequired, Unpack

from .edges import get_edges
from .names import get_name, get_references
from .properties import get_literal_properties
from .utils import _get_pi
from ..constants import GetOntologyKwargs
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

    include_part_of: NotRequired[bool]
    include_has_member: NotRequired[bool]


def get_hierarchy(
    prefix: str,
    *,
    extra_relations: Iterable[ReferenceHint] | None = None,
    properties: Iterable[ReferenceHint] | None = None,
    **kwargs: Unpack[HierarchyKwargs],
) -> nx.DiGraph:
    """Get hierarchy of parents as a directed graph.

    :param prefix: The name of the namespace.
    :param include_part_of: Add "part of" relations. Only works if the relations are
        properly defined using bfo:0000050 ! part of or bfo:0000051 ! has part
    :param include_has_member: Add "has member" relations. These aren't part of the BFO,
        but are hacked into PyOBO using :data:`pyobo.struct.typedef.has_member` for
        relationships like from protein families to their actual proteins.
    :param extra_relations: Other relations that you want to include in the hierarchy.
        For example, it might be useful to include the positively_regulates
    :param properties: Properties to include in the data part of each node. For example,
        might want to include SMILES strings with the ChEBI tree.
    :param force: should the resources be reloaded when extracting relations?

    :returns: A directional graph representing the hierarchy

    This function thinly wraps :func:`_get_hierarchy_helper` to make it easier to work
    with the lru_cache mechanism.
    """
    return _get_hierarchy_helper(
        prefix=prefix,
        extra_relations=_tp(prefix, extra_relations),
        properties=_tp(prefix, properties),
        **kwargs,
    )


def _tp(prefix: str, references: Iterable[ReferenceHint] | None) -> tuple[Reference, ...]:
    return tuple(
        sorted(_ensure_ref(reference, ontology_prefix=prefix) for reference in references or [])
    )


@lru_cache
def _get_hierarchy_helper(
    prefix: str,
    *,
    extra_relations: tuple[Reference, ...],
    properties: tuple[Reference, ...],
    include_part_of: bool = False,
    include_has_member: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> nx.DiGraph:
    predicates, reverse_predicates = _get_predicate_sets(
        extra_relations, include_part_of, include_has_member
    )

    rv = nx.DiGraph()
    rv.add_nodes_from(get_references(prefix, **kwargs))

    for s, p, o in get_edges(prefix, **kwargs):
        if p in predicates:
            rv.add_edge(s, o, relation=p)
        elif p in reverse_predicates:
            rv.add_edge(o, s, relation=p)

    properties_ = set(properties)
    for s, p, op in get_literal_properties(prefix, **kwargs):
        if s in rv and p in properties_:
            rv.nodes[s][p] = op.value

    return rv


def _get_predicate_sets(
    extra_relations: Iterable[Reference], include_part_of: bool, include_has_member: bool
) -> tuple[set[Reference], set[Reference]]:
    predicates: set[Reference] = {is_a.reference, *extra_relations}
    reverse_predicates: set[Reference] = set()
    if include_part_of:
        predicates.add(part_of.reference)
        reverse_predicates.add(has_part.reference)
    if include_has_member:
        predicates.add(has_member.reference)
        reverse_predicates.add(member_of.reference)
    return predicates, reverse_predicates


# docstr-coverage:excused `overload`
@overload
def is_descendent(
    prefix: str,
    identifier: str,
    ancestor_prefix: str = ...,
    ancestor_identifier: str = ...,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool: ...


# docstr-coverage:excused `overload`
@overload
def is_descendent(
    descendant: Reference,
    ancestor: Reference,
    _1: None = ...,
    _2: None = ...,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool: ...


def is_descendent(
    prefix: str | Reference,
    identifier: str | Reference,
    ancestor_prefix: str | None = None,
    ancestor_identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool:
    """Check that the first identifier has the second as a descendent.

    :param prefix: The prefix for the descendant
    :param identifier: The local unique identifier for the descendant
    :param ancestor_prefix: The prefix for the ancestor
    :param ancestor_identifier: The local unique identifier for the ancestor
    :param kwargs: Keyword arguments for :func:`get_hierarchy`
    :return: If the decendant has the given ancestor

    Check that ``GO:0070246`` (natural killer cell apoptotic process) is a descendant of
    ``GO:0006915`` (apoptotic process)

    >>> nk_apoptosis = Reference.from_curie(
    ...     "GO:0070246", name="natural killer cell apoptotic process"
    ... )
    >>> apoptosis = Reference.from_curie("GO:0006915", name="apoptotic process")
    >>> assert is_descendent(nk_apoptosis, apoptosis)

    Using deprecated old-style arguments:

    >>> assert is_descendent("go", "0070246", "go", "0006915")
    """
    descendant, ancestor = _get_double_reference(
        prefix, identifier, ancestor_prefix, ancestor_identifier
    )
    descendants = get_descendants(ancestor, **kwargs)
    return descendants is not None and descendant in descendants


@lru_cache
def get_descendants(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[Reference] | None:
    """Get all the descendants (children) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t not in hierarchy:
        return None
    return nx.ancestors(hierarchy, t)  # note this is backwards


@lru_cache
def get_children(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[Reference] | None:
    """Get all the descendants (children) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t not in hierarchy:
        return None
    return set(hierarchy.predecessors(t))


# docstr-coverage:excused `overload`
@overload
def has_ancestor(
    prefix: str,
    identifier: str,
    ancestor_prefix: str = ...,
    ancestor_identifier: str = ...,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool: ...


# docstr-coverage:excused `overload`
@overload
def has_ancestor(
    descendant: Reference,
    ancestor: Reference,
    _1: None = ...,
    _2: None = ...,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool: ...


def has_ancestor(
    prefix: str | Reference,
    identifier: str | Reference,
    ancestor_prefix: str | None = None,
    ancestor_identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> bool:
    """Check that the first identifier has the second as an ancestor.

    :param prefix: The prefix for the descendant
    :param identifier: The local unique identifier for the descendant
    :param ancestor_prefix: The prefix for the ancestor
    :param ancestor_identifier: The local unique identifier for the ancestor
    :param kwargs: Keyword arguments for :func:`get_hierarchy`
    :return: If the decendant has the given ancestor

    Check that ``GO:0008219`` (cell death) is an ancestor of ``GO:0006915``
    (apoptotic process):

    >>> apoptosis = Reference.from_curie("GO:0006915", name="apoptotic process")
    >>> cell_death = Reference.from_curie("GO:0008219", name="cell death")
    >>> assert has_ancestor(apoptosis, cell_death)

    The same, using the deprecated argumentation style:

    >>> assert has_ancestor("go", "0006915", "go", "0008219")
    """
    descendant, ancestor = _get_double_reference(
        prefix, identifier, ancestor_prefix, ancestor_identifier
    )
    ancestors = get_ancestors(descendant, **kwargs)
    return ancestors is not None and ancestor in ancestors


def _get_double_reference(
    a: str | Reference, b: str | Reference, c: str | None, d: str | None
) -> tuple[Reference, Reference]:
    if isinstance(a, Reference) and isinstance(b, Reference):
        return a, b
    elif all(isinstance(x, str) for x in (a, b, c, d)):
        warnings.warn("passing strings is deprecated", DeprecationWarning, stacklevel=2)
        return Reference(prefix=a, identifier=b), Reference(prefix=c, identifier=d)
    else:
        raise TypeError


@lru_cache
def get_ancestors(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> set[Reference] | None:
    """Get all the ancestors (parents) of the term as CURIEs."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    if t not in hierarchy:
        return None

    return nx.descendants(hierarchy, t)  # note this is backwards


def get_subhierarchy(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[HierarchyKwargs],
) -> nx.DiGraph:
    """Get the subhierarchy for a given node."""
    t = _get_pi(prefix, identifier)
    hierarchy = get_hierarchy(prefix=t.prefix, **kwargs)
    logger.info("getting descendants of %s ! %s", t.curie, get_name(t))
    descendants = set(nx.ancestors(hierarchy, t)) | {t}  # note this is backwards
    logger.info("inducing subgraph")
    sg = hierarchy.subgraph(descendants).copy()
    logger.info("subgraph has %d nodes/%d edges", sg.number_of_nodes(), sg.number_of_edges())
    return sg
