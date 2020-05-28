# -*- coding: utf-8 -*-

"""High level API for extracting OBO content."""

import logging
import os
from functools import lru_cache
from typing import Iterable, List, Mapping, Optional, Tuple, Union

import networkx as nx
import pandas as pd

from .cache_utils import cached_df, cached_mapping, cached_multidict
from .constants import GLOBAL_SKIP, PYOBO_HOME
from .getters import NoOboFoundry, get
from .identifier_utils import normalize_curie
from .path_utils import prefix_directory_join
from .registries import NOT_AVAILABLE_AS_OBO, OBSOLETE
from .struct import Reference, TypeDef, get_reference_tuple
from .struct.typedef import has_member, is_a, part_of

__all__ = [
    # Nomenclature
    'get_name_id_mapping',
    'get_id_name_mapping',
    # Synonyms
    'get_id_synonyms_mapping',
    # Properties
    'get_properties_df',
    'get_filtered_properties_df',
    'get_filtered_properties_mapping',
    # Relations
    'get_filtered_relations_df',
    'get_id_multirelations_mapping',
    'get_relations_df',
    # Xrefs
    'get_filtered_xrefs',
    'get_xrefs_df',
    # Hierarchy
    'get_hierarchy',
    'get_subhierarchy',
    'get_descendants',
    'get_ancestors',
    # misc
    'iter_cached_obo',
]

logger = logging.getLogger(__name__)

RelationHint = Union[Reference, TypeDef, Tuple[str, str]]


def get_name_by_curie(curie: str) -> Optional[str]:
    """Get the name for a CURIE, if possible."""
    prefix, identifier = normalize_curie(curie)
    if prefix and identifier:
        return get_name(prefix, identifier)


def get_name(prefix: str, identifier: str) -> Optional[str]:
    """Get the name for an entity."""
    try:
        id_name = get_id_name_mapping(prefix)
    except NoOboFoundry:
        return  # sorry, this namespace isn't available at all
    if id_name:
        return id_name.get(identifier)


@lru_cache()
def get_id_name_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == 'ncbigene':
        from .sources.ncbigene import get_ncbigene_id_to_name_mapping
        logger.info('[%s] loading mappings', prefix)
        return get_ncbigene_id_to_name_mapping()
    elif prefix == 'taxonomy':
        prefix = 'ncbitaxon'

    path = prefix_directory_join(prefix, 'cache', "names.tsv")

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'])
    def _get_id_name_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        logger.info('[%s] loading mappings', prefix)
        return obo.get_id_name_mapping()

    return _get_id_name_mapping()


@lru_cache()
def get_name_id_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    return {
        name: identifier
        for identifier, name in get_id_name_mapping(prefix=prefix, **kwargs).items()
    }


def get_id_synonyms_mapping(prefix: str, **kwargs) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, 'cache', "synonyms.tsv")
    header = [f'{prefix}_id', 'synonym']

    @cached_multidict(path=path, header=header)
    def _get_multidict() -> Mapping[str, List[str]]:
        obo = get(prefix, **kwargs)
        return obo.get_id_synonyms_mapping()

    return _get_multidict()


def get_properties_df(prefix: str, **kwargs) -> pd.DataFrame:
    """Extract properties."""
    path = prefix_directory_join(prefix, 'cache', "properties.tsv")

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        df = obo.get_properties_df()
        df.dropna(inplace=True)
        return df

    return _df_getter()


def get_filtered_properties_mapping(prefix: str, prop: str, use_tqdm: bool = False, **kwargs) -> Mapping[str, str]:
    """Extract a single property for each term as a dictionary."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")

    @cached_mapping(path=path, header=[f'{prefix}_id', prop])
    def _mapping_getter() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_mapping(prop, use_tqdm=use_tqdm)

    return _mapping_getter()


def get_filtered_properties_df(prefix: str, prop: str, *, use_tqdm: bool = False, **kwargs) -> pd.DataFrame:
    """Extract a single property for each term."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_df(prop, use_tqdm=use_tqdm)

    return _df_getter()


def get_relations_df(prefix: str, *, use_tqdm: bool = False, **kwargs) -> pd.DataFrame:
    """Get all relations from the OBO."""
    path = prefix_directory_join(prefix, 'cache', 'relations.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_relations_df(use_tqdm=use_tqdm)

    return _df_getter()


def get_filtered_relations_df(
    prefix: str,
    relation: RelationHint,
    *,
    use_tqdm: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Get all of the given relation."""
    relation = get_reference_tuple(relation)
    path = prefix_directory_join(prefix, 'cache', 'relations', f'{relation[0]}:{relation[1]}.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_relations_df(relation, use_tqdm=use_tqdm)

    return _df_getter()


def get_id_multirelations_mapping(
    prefix: str,
    type_def: TypeDef,
    *,
    use_tqdm: bool = False,
    **kwargs,
) -> Mapping[str, List[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    obo = get(prefix, **kwargs)
    return obo.get_id_multirelations_mapping(type_def, use_tqdm=use_tqdm)


@lru_cache()
def get_filtered_xrefs(
    prefix: str,
    xref_prefix: str,
    flip: bool = False,
    *,
    use_tqdm: bool = False,
    **kwargs,
) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    path = prefix_directory_join(prefix, 'cache', 'xrefs', f"{xref_prefix}.tsv")
    header = [f'{prefix}_id', f'{xref_prefix}_id']

    @cached_mapping(path=path, header=header, use_tqdm=use_tqdm)
    def _get_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        return obo.get_filtered_xrefs_mapping(xref_prefix, use_tqdm=use_tqdm)

    rv = _get_mapping()
    if flip:
        return {v: k for k, v in rv.items()}
    return rv


def get_xrefs_df(prefix: str, *, use_tqdm: bool = False, **kwargs) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_directory_join(prefix, 'cache', 'xrefs.tsv')

    @cached_df(path=path, dtype=str)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_xrefs_df(use_tqdm=use_tqdm)

    return _df_getter()


def get_hierarchy(
    prefix: str,
    *,
    include_part_of: bool = True,
    include_has_member: bool = False,
    extra_relations: Optional[Iterable[RelationHint]] = None,
    properties: Optional[Iterable[str]] = None,
    use_tqdm: bool = False,
    **kwargs,
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

    This function thinly wraps :func:`_get_hierarchy_helper` to make it easier to work with the lru_cache mechanism.
    """
    return _get_hierarchy_helper(
        prefix=prefix,
        include_part_of=include_part_of,
        include_has_member=include_has_member,
        extra_relations=tuple(sorted(extra_relations or [])),
        properties=tuple(sorted(properties or [])),
        use_tqdm=use_tqdm,
        **kwargs,
    )


@lru_cache()
def _get_hierarchy_helper(
    *,
    prefix: str,
    extra_relations: Tuple[RelationHint, ...],
    properties: Tuple[str, ...],
    include_part_of: bool,
    include_has_member: bool,
    use_tqdm: bool,
    **kwargs,
) -> nx.DiGraph:
    rv = nx.DiGraph()

    is_a_df = get_filtered_relations_df(prefix=prefix, relation=is_a, use_tqdm=use_tqdm, **kwargs)
    for source_id, target_ns, target_id in is_a_df.values:
        rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation='is_a')

    if include_has_member:
        has_member_df = get_filtered_relations_df(prefix, relation=has_member, use_tqdm=use_tqdm, **kwargs)
        for target_id, source_ns, source_id in has_member_df.values:
            rv.add_edge(f'{source_ns}:{source_id}', f'{prefix}:{target_id}', relation='is_a')

    if include_part_of:
        part_of_df = get_filtered_relations_df(prefix=prefix, relation=part_of, use_tqdm=use_tqdm, **kwargs)
        for source_id, target_ns, target_id in part_of_df.values:
            rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation='part_of')

        has_part_df = get_filtered_relations_df(prefix=prefix, relation=part_of, use_tqdm=use_tqdm, **kwargs)
        for target_id, source_ns, source_id in has_part_df.values:
            rv.add_edge(f'{source_ns}:{source_id}', f'{prefix}:{target_id}', relation='part_of')

    for relation in extra_relations:
        relation_df = get_filtered_relations_df(prefix=prefix, relation=relation, use_tqdm=use_tqdm, **kwargs)
        for source_id, target_ns, target_id in relation_df.values:
            rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation=relation.identifier)

    for prop in properties:
        props = get_filtered_properties_mapping(prefix=prefix, prop=prop, use_tqdm=use_tqdm)
        for identifier, value in props.items():
            curie = f'{prefix}:{identifier}'
            if curie in rv:
                rv.nodes[curie][prop] = value

    return rv


def get_descendants(
    prefix,
    identifier,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    **kwargs,
) -> List[str]:
    """Get all of the descendants (children) of the term as CURIEs."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        **kwargs,
    )
    return nx.ancestors(hierarchy, f'{prefix}:{identifier}')  # note this is backwards


def get_ancestors(
    prefix: str,
    identifier: str,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    **kwargs,
) -> List[str]:
    """Get all of the ancestors (parents) of the term as CURIEs."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        **kwargs,
    )
    return nx.descendants(hierarchy, f'{prefix}:{identifier}')  # note this is backwards


def get_subhierarchy(
    prefix: str,
    identifier: str,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    **kwargs,
) -> nx.DiGraph:
    """Get the subhierarchy for a given node."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        **kwargs,
    )
    logger.info('getting descendants of %s:%s', prefix, identifier)
    curies = nx.ancestors(hierarchy, f'{prefix}:{identifier}')  # note this is backwards
    logger.info('inducing subgraph')
    sg = hierarchy.subgraph(curies).copy()
    logger.info('subgraph has %d nodes/%d edges', sg.number_of_nodes(), sg.number_of_edges())
    return sg


def iter_cached_obo() -> List[Tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(PYOBO_HOME):
        if prefix in GLOBAL_SKIP or prefix in NOT_AVAILABLE_AS_OBO or prefix in OBSOLETE:
            continue
        d = os.path.join(PYOBO_HOME, prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith('.obo'):
                p = os.path.join(d, x)
                yield prefix, p
