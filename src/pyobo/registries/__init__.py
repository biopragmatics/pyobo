# -*- coding: utf-8 -*-

"""Extract registry information."""

from .registries import (  # noqa: F401
    CURATED_REGISTRY, CURATED_URLS, REMAPPINGS_PREFIX, Resource, XREF_BLACKLIST, XREF_PREFIX_BLACKLIST,
    XREF_SUFFIX_BLACKLIST, get_curated_registry, get_metaregistry, get_miriam, get_namespace_synonyms, get_obofoundry,
    get_ols,
)
