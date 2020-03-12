# -*- coding: utf-8 -*-

"""Extract registry information."""

from .registries import (
    get_curated_registry, get_metaregistry, get_miriam, get_namespace_synonyms, get_obofoundry, get_ols,
)

__all__ = [
    'get_curated_registry',
    'get_metaregistry',
    'get_miriam',
    'get_namespace_synonyms',
    'get_obofoundry',
    'get_ols',
]
