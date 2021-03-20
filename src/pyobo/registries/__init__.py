# -*- coding: utf-8 -*-

"""Extract registry information."""

from .metaregistry import (  # noqa: F401
    get_curated_urls, get_prefix_to_miriam_prefix, get_prefix_to_obofoundry_prefix, get_prefix_to_ols_prefix,
    get_remappings_full, get_remappings_prefix, get_wikidata_property_types, get_xrefs_blacklist,
    get_xrefs_prefix_blacklist, get_xrefs_suffix_blacklist, iter_cached_obo, not_available_as_obo, remap_full,
)
