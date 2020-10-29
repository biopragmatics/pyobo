# -*- coding: utf-8 -*-

"""Extract registry information."""

from .metaregistry import (  # noqa: F401
    get_curated_registry_database, get_curated_urls, get_not_available_as_obo, get_obsolete,
    get_prefix_to_miriam_prefix, get_remappings_prefix, get_wikidata_property_types, get_xrefs_blacklist,
    get_xrefs_prefix_blacklist, get_xrefs_suffix_blacklist,
)
from .miriam import get_miriam  # noqa: F401
from .obofoundry import get_obofoundry  # noqa: F401
from .ols import get_ols  # noqa: F401
from .registries import Resource, get_namespace_synonyms  # noqa: F401
