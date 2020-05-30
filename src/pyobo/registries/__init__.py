# -*- coding: utf-8 -*-

"""Extract registry information."""

from .metaregistry import (  # noqa: F401
    CURATED_REGISTRY, CURATED_URLS, NOT_AVAILABLE_AS_OBO, OBSOLETE, PREFIX_TO_MIRIAM_PREFIX, REMAPPINGS_PREFIX,
    XREF_BLACKLIST, XREF_PREFIX_BLACKLIST, XREF_SUFFIX_BLACKLIST, get_curated_registry,
)
from .miriam import get_miriam  # noqa: F401
from .obofoundry import get_obofoundry  # noqa: F401
from .ols import get_ols  # noqa: F401
from .registries import Resource, get_metaregistry, get_namespace_synonyms  # noqa: F401
