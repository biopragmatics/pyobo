# -*- coding: utf-8 -*-

"""High-level API for typedefs."""

import logging
from functools import lru_cache
from typing import Mapping

from .utils import get_version
from ..getters import get
from ..identifier_utils import wrap_norm_prefix
from ..path_utils import prefix_cache_join
from ..utils.cache import cached_mapping

__all__ = [
    'get_typedef_id_name_mapping',
]

logger = logging.getLogger(__name__)


@lru_cache()
@wrap_norm_prefix
def get_typedef_id_name_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get an identifier to name mapping for the typedefs in an OBO file."""
    path = prefix_cache_join(prefix, 'typedefs.tsv', version=get_version(prefix))

    @cached_mapping(path=path, header=[f'{prefix}_id', 'name'], force=force)
    def _get_typedef_id_name_mapping() -> Mapping[str, str]:
        logger.info('[%s] no cached typedefs found. getting from OBO loader', prefix)
        obo = get(prefix, force=force)
        logger.info('[%s] loading typedef mappings', prefix)
        return obo.get_typedef_id_name_mapping()

    return _get_typedef_id_name_mapping()
