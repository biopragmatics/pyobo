"""Extract registry information."""

from .metaregistry import (  # noqa: F401
    curie_has_blacklisted_prefix,
    curie_has_blacklisted_suffix,
    curie_is_blacklisted,
    get_remappings_full,
    get_remappings_prefix,
    get_xrefs_blacklist,
    get_xrefs_prefix_blacklist,
    get_xrefs_suffix_blacklist,
    has_no_download,
    iter_cached_obo,
    remap_full,
    remap_prefix,
)
