# -*- coding: utf-8 -*-

"""High-level API for nomenclature."""

import logging
from functools import lru_cache
from typing import List, Mapping, Optional

from .alts import get_primary_identifier
from .utils import get_version
from ..cache_utils import cached_mapping, cached_multidict
from ..getters import NoOboFoundry, get
from ..identifier_utils import normalize_curie, wrap_norm_prefix
from ..path_utils import prefix_cache_join

__all__ = [
    'get_name',
    'get_name_by_curie',
    'get_id_name_mapping',
    'get_name_id_mapping',
    'get_id_synonyms_mapping',
]

logger = logging.getLogger(__name__)


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
        logger.warning('unable to look up names for prefix %s', prefix)
        return

    primary_id = get_primary_identifier(prefix, identifier)
    return id_name.get(primary_id)


@lru_cache()
@wrap_norm_prefix
def get_id_name_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == 'ncbigene':
        from ..sources.ncbigene import get_ncbigene_id_to_name_mapping
        logger.info('[%s] loading name mappings', prefix)
        rv = get_ncbigene_id_to_name_mapping()
        logger.info('[%s] done loading name mappings', prefix)
        return rv

    path = prefix_cache_join(prefix, 'names.tsv', version=get_version(prefix))

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'], force=force)
    def _get_id_name_mapping() -> Mapping[str, str]:
        if force:
            logger.info('[%s] forcing reload for names', prefix)
        else:
            logger.info('[%s] no cached names found. getting from OBO loader', prefix)
        obo = get(prefix, force=force)
        return obo.get_id_name_mapping()

    return _get_id_name_mapping()


@lru_cache()
@wrap_norm_prefix
def get_name_id_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    return {
        name: identifier
        for identifier, name in get_id_name_mapping(prefix=prefix, force=force).items()
    }


@wrap_norm_prefix
def get_id_synonyms_mapping(prefix: str, force: bool = False) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_cache_join(prefix, "synonyms.tsv", version=get_version(prefix))

    @cached_multidict(path=path, header=[f'{prefix}_id', 'synonym'], force=force)
    def _get_multidict() -> Mapping[str, List[str]]:
        logger.info('[%s] no cached synonyms found. getting from OBO loader', prefix)
        obo = get(prefix, force=force)
        return obo.get_id_synonyms_mapping()

    return _get_multidict()
