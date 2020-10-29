# -*- coding: utf-8 -*-

"""High level API for extracting OBO content."""

import logging
import os
from functools import lru_cache
from typing import Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx
import pandas as pd

from .cache_utils import cached_df, cached_mapping, cached_multidict
from .constants import (
    GLOBAL_SKIP, RAW_DIRECTORY, RELATION_COLUMNS, RELATION_ID, RELATION_PREFIX, SOURCE_ID, SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)
from .getters import NoOboFoundry, get
from .identifier_utils import normalize_curie, wrap_norm_prefix
from .path_utils import prefix_directory_join
from .registries import get_not_available_as_obo, get_obsolete
from .struct import Reference, TypeDef, get_reference_tuple
from .struct.typedef import has_member, is_a, part_of

__all__ = [
    # Nomenclature
    'get_name_id_mapping',
    'get_id_name_mapping',
    'get_name',
    'get_name_by_curie',
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
    # Alt ids
    'get_id_to_alts',
    'get_alts_to_id',
    'get_primary_identifier',
    'get_primary_curie',
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

NO_ALTS = {'ncbigene'}


def get_name_by_curie(curie: str) -> Optional[str]:
    """Get the name for a CURIE, if possible."""
    prefix, identifier = normalize_curie(curie)
    if prefix and identifier:
        return get_name(prefix, identifier)


@wrap_norm_prefix
def get_name(prefix: str, identifier: str) -> Optional[str]:
    """Get the name for an entity."""
    if prefix == 'uniprot':
        from protmapper import uniprot_client
        return uniprot_client.get_mnemonic(identifier)

    try:
        id_name = get_id_name_mapping(prefix)
    except NoOboFoundry:
        id_name = None

    if not id_name:
        logger.warning('unable to look up prefix %s', prefix)
        return

    primary_id = get_primary_identifier(prefix, identifier)
    return id_name.get(primary_id)


@lru_cache()
@wrap_norm_prefix
def get_id_name_mapping(prefix: str, force: bool = False, **kwargs) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == 'ncbigene':
        from .sources.ncbigene import get_ncbigene_id_to_name_mapping
        logger.info('[%s] loading mappings', prefix)
        return get_ncbigene_id_to_name_mapping()

    path = prefix_directory_join(prefix, 'cache', 'names.tsv')

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'], force=force)
    def _get_id_name_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        logger.info('[%s] loading mappings', prefix)
        return obo.get_id_name_mapping()

    return _get_id_name_mapping()


@lru_cache()
@wrap_norm_prefix
def get_name_id_mapping(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    return {
        name: identifier
        for identifier, name in get_id_name_mapping(prefix=prefix, **kwargs).items()
    }


@lru_cache()
@wrap_norm_prefix
def get_typedef_id_name_mapping(prefix: str, force: bool = False, **kwargs) -> Mapping[str, str]:
    """Get an identifier to name mapping for the typedefs in an OBO file."""
    path = prefix_directory_join(prefix, 'cache', 'typedefs.tsv')

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'], force=force)
    def _get_typedef_id_name_mapping() -> Mapping[str, str]:
        obo = get(prefix, **kwargs)
        logger.info('[%s] loading typedef mappings', prefix)
        return obo.get_typedef_id_name_mapping()

    return _get_typedef_id_name_mapping()


@wrap_norm_prefix
def get_id_synonyms_mapping(prefix: str, force: bool = False, **kwargs) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, 'cache', "synonyms.tsv")
    header = [f'{prefix}_id', 'synonym']

    @cached_multidict(path=path, header=header, force=force)
    def _get_multidict() -> Mapping[str, List[str]]:
        obo = get(prefix, **kwargs)
        return obo.get_id_synonyms_mapping()

    return _get_multidict()


@wrap_norm_prefix
def get_properties_df(prefix: str, force: bool = False, **kwargs) -> pd.DataFrame:
    """Extract properties."""
    path = prefix_directory_join(prefix, 'cache', "properties.tsv")

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        df = obo.get_properties_df()
        df.dropna(inplace=True)
        return df

    return _df_getter()


@wrap_norm_prefix
def get_filtered_properties_mapping(
    prefix: str,
    prop: str,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Mapping[str, str]:
    """Extract a single property for each term as a dictionary."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")
    all_properties_path = prefix_directory_join(prefix, 'cache', 'properties.tsv')

    @cached_mapping(path=path, header=[f'{prefix}_id', prop], force=force)
    def _mapping_getter() -> Mapping[str, str]:
        if os.path.exists(all_properties_path):
            logger.info('[%s] loading pre-cached properties', prefix)
            df = pd.read_csv(all_properties_path, sep='\t')
            logger.info('[%s] filtering pre-cached properties', prefix)
            df = df.loc[df['property'] == prop, [f'{prefix}_id', 'value']]
            return dict(df.values)

        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_mapping(prop, use_tqdm=use_tqdm)

    return _mapping_getter()


@wrap_norm_prefix
def get_filtered_properties_df(
    prefix: str,
    prop: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Extract a single property for each term."""
    path = prefix_directory_join(prefix, 'cache', 'properties', f"{prop}.tsv")
    all_properties_path = prefix_directory_join(prefix, 'cache', 'properties.tsv')

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if os.path.exists(all_properties_path):
            logger.info('[%s] loading pre-cached properties', prefix)
            df = pd.read_csv(all_properties_path, sep='\t')
            logger.info('[%s] filtering pre-cached properties', prefix)
            return df.loc[df['property'] == prop, [f'{prefix}_id', 'value']]

        obo = get(prefix, **kwargs)
        return obo.get_filtered_properties_df(prop, use_tqdm=use_tqdm)

    return _df_getter()


@wrap_norm_prefix
def get_relations_df(
    prefix: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    wide: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Get all relations from the OBO."""
    path = prefix_directory_join(prefix, 'cache', 'relations.tsv')

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_relations_df(use_tqdm=use_tqdm)

    rv = _df_getter()

    if wide:
        rv = rv.rename(columns={f'{prefix}_id': SOURCE_ID})
        rv[SOURCE_PREFIX] = prefix
        rv = rv[RELATION_COLUMNS]

    return rv


@wrap_norm_prefix
def get_filtered_relations_df(
    prefix: str,
    relation: RelationHint,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Get all of the given relation."""
    relation_prefix, relation_identifier = relation = get_reference_tuple(relation)
    path = prefix_directory_join(prefix, 'cache', 'relations', f'{relation_prefix}:{relation_identifier}.tsv')
    all_relations_path = prefix_directory_join(prefix, 'cache', 'relations.tsv')

    # chebi_id        relation_ns     relation_id     target_ns       target_id

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if os.path.exists(all_relations_path):
            df = pd.read_csv(all_relations_path, sep='\t')
            idx = (df[RELATION_PREFIX] == relation_prefix) & (df[RELATION_ID] == relation_identifier)
            columns = [f'{prefix}_id', TARGET_PREFIX, TARGET_ID]
            return df.loc[idx, columns]

        obo = get(prefix, **kwargs)
        return obo.get_filtered_relations_df(relation, use_tqdm=use_tqdm)

    return _df_getter()


@wrap_norm_prefix
def get_id_multirelations_mapping(
    prefix: str,
    typedef: TypeDef,
    *,
    use_tqdm: bool = False,
    **kwargs,
) -> Mapping[str, List[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    obo = get(prefix, **kwargs)
    return obo.get_id_multirelations_mapping(typedef=typedef, use_tqdm=use_tqdm)


@lru_cache()
@wrap_norm_prefix
def get_filtered_xrefs(
    prefix: str,
    xref_prefix: str,
    flip: bool = False,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    path = prefix_directory_join(prefix, 'cache', 'xrefs', f"{xref_prefix}.tsv")
    all_xrefs_path = prefix_directory_join(prefix, 'cache', 'xrefs.tsv')
    header = [f'{prefix}_id', f'{xref_prefix}_id']

    @cached_mapping(path=path, header=header, use_tqdm=use_tqdm, force=force)
    def _get_mapping() -> Mapping[str, str]:
        if os.path.exists(all_xrefs_path):
            logger.info('[%s] loading pre-cached xrefs', prefix)
            df = pd.read_csv(all_xrefs_path, sep='\t')
            logger.info('[%s] filtering pre-cached xrefs', prefix)
            idx = (df[SOURCE_PREFIX] == prefix) & (df[TARGET_PREFIX] == xref_prefix)
            df = df.loc[idx, [SOURCE_ID, TARGET_ID]]
            return dict(df.values)

        obo = get(prefix, **kwargs)
        return obo.get_filtered_xrefs_mapping(xref_prefix, use_tqdm=use_tqdm)

    rv = _get_mapping()
    if flip:
        return {v: k for k, v in rv.items()}
    return rv


@wrap_norm_prefix
def get_xrefs_df(prefix: str, *, use_tqdm: bool = False, force: bool = False, **kwargs) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_directory_join(prefix, 'cache', 'xrefs.tsv')

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        obo = get(prefix, **kwargs)
        return obo.get_xrefs_df(use_tqdm=use_tqdm)

    return _df_getter()


@lru_cache()
@wrap_norm_prefix
def get_id_to_alts(prefix: str, force: bool = False, **kwargs) -> Mapping[str, List[str]]:
    """Get alternate identifiers."""
    if prefix in NO_ALTS:
        return {}

    path = prefix_directory_join(prefix, 'cache', 'alt_ids.tsv')
    header = [f'{prefix}_id', 'alt_id']

    @cached_multidict(path=path, header=header, force=force)
    def _get_mapping() -> Mapping[str, List[str]]:
        obo = get(prefix, **kwargs)
        return obo.get_id_alts_mapping()

    return _get_mapping()


@lru_cache()
@wrap_norm_prefix
def get_alts_to_id(prefix: str, **kwargs) -> Mapping[str, str]:
    """Get alternative id to primary id mapping."""
    return {
        alt: primary
        for primary, alts in get_id_to_alts(prefix, **kwargs).items()
        for alt in alts
    }


def get_primary_curie(curie: str) -> Optional[str]:
    """Get the primary curie for an entity."""
    prefix, identifier = normalize_curie(curie)
    primary_identifier = get_primary_identifier(prefix, identifier)
    if primary_identifier is not None:
        return f'{prefix}:{primary_identifier}'


@wrap_norm_prefix
def get_primary_identifier(prefix: str, identifier: str) -> str:
    """Get the primary identifier for an entity.

    Returns the original identifier if there are no alts available or if there's no mapping.
    """
    if prefix in NO_ALTS:  # TODO later expand list to other namespaces with no alts
        return identifier

    alts_to_id = get_alts_to_id(prefix)
    if alts_to_id and identifier in alts_to_id:
        return alts_to_id[identifier]
    return identifier


def get_hierarchy(
    prefix: str,
    *,
    include_part_of: bool = True,
    include_has_member: bool = False,
    extra_relations: Optional[Iterable[RelationHint]] = None,
    properties: Optional[Iterable[str]] = None,
    use_tqdm: bool = False,
    force: bool = False,
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
        force=force,
        **kwargs,
    )


@lru_cache()
@wrap_norm_prefix
def _get_hierarchy_helper(
    prefix: str,
    *,
    extra_relations: Tuple[RelationHint, ...],
    properties: Tuple[str, ...],
    include_part_of: bool,
    include_has_member: bool,
    use_tqdm: bool,
    force: bool = False,
    **kwargs,
) -> nx.DiGraph:
    rv = nx.DiGraph()

    is_a_df = get_filtered_relations_df(
        prefix=prefix,
        relation=is_a,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    for source_id, target_ns, target_id in is_a_df.values:
        rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation='is_a')

    if include_has_member:
        has_member_df = get_filtered_relations_df(
            prefix=prefix,
            relation=has_member,
            use_tqdm=use_tqdm,
            force=force,
            **kwargs,
        )
        for target_id, source_ns, source_id in has_member_df.values:
            rv.add_edge(f'{source_ns}:{source_id}', f'{prefix}:{target_id}', relation='is_a')

    if include_part_of:
        part_of_df = get_filtered_relations_df(
            prefix=prefix,
            relation=part_of,
            use_tqdm=use_tqdm,
            force=force,
            **kwargs,
        )
        for source_id, target_ns, target_id in part_of_df.values:
            rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation='part_of')

        has_part_df = get_filtered_relations_df(
            prefix=prefix,
            relation=part_of,
            use_tqdm=use_tqdm,
            force=force,
            **kwargs,
        )
        for target_id, source_ns, source_id in has_part_df.values:
            rv.add_edge(f'{source_ns}:{source_id}', f'{prefix}:{target_id}', relation='part_of')

    for relation in extra_relations:
        relation_df = get_filtered_relations_df(
            prefix=prefix,
            relation=relation,
            use_tqdm=use_tqdm,
            force=force,
            **kwargs,
        )
        for source_id, target_ns, target_id in relation_df.values:
            rv.add_edge(f'{prefix}:{source_id}', f'{target_ns}:{target_id}', relation=relation.identifier)

    for prop in properties:
        props = get_filtered_properties_mapping(prefix=prefix, prop=prop, use_tqdm=use_tqdm, force=force)
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
    force: bool = False,
    **kwargs,
) -> Set[str]:
    """Get all of the descendants (children) of the term as CURIEs."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    return nx.ancestors(hierarchy, f'{prefix}:{identifier}')  # note this is backwards


def get_ancestors(
    prefix: str,
    identifier: str,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> Set[str]:
    """Get all of the ancestors (parents) of the term as CURIEs."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    return nx.descendants(hierarchy, f'{prefix}:{identifier}')  # note this is backwards


def get_subhierarchy(
    prefix: str,
    identifier: str,
    include_part_of: bool = True,
    include_has_member: bool = False,
    use_tqdm: bool = False,
    force: bool = False,
    **kwargs,
) -> nx.DiGraph:
    """Get the subhierarchy for a given node."""
    hierarchy = get_hierarchy(
        prefix=prefix,
        include_has_member=include_has_member,
        include_part_of=include_part_of,
        use_tqdm=use_tqdm,
        force=force,
        **kwargs,
    )
    logger.info('getting descendants of %s:%s ! %s', prefix, identifier, get_name(prefix, identifier))
    curies = nx.ancestors(hierarchy, f'{prefix}:{identifier}')  # note this is backwards
    logger.info('inducing subgraph')
    sg = hierarchy.subgraph(curies).copy()
    logger.info('subgraph has %d nodes/%d edges', sg.number_of_nodes(), sg.number_of_edges())
    return sg


def iter_cached_obo() -> List[Tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(RAW_DIRECTORY):
        if prefix in GLOBAL_SKIP or prefix in get_not_available_as_obo() or prefix in get_obsolete():
            continue
        d = os.path.join(RAW_DIRECTORY, prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith('.obo'):
                p = os.path.join(d, x)
                yield prefix, p
