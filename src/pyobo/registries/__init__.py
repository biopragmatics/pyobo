# -*- coding: utf-8 -*-

"""Extract registry information."""

from .metaregistry import (  # noqa: F401
    get_remappings_full,
    get_remappings_prefix,
    get_wikidata_property_types,
    get_xrefs_blacklist,
    get_xrefs_prefix_blacklist,
    get_xrefs_suffix_blacklist,
    iter_cached_obo,
    has_no_download,
    remap_full,
)
