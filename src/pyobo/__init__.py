# -*- coding: utf-8 -*-

"""A python package for handling and generating OBO."""

from .extract import (  # noqa: F401
    get_alts_to_id, get_ancestors, get_descendants, get_filtered_properties_mapping, get_filtered_xrefs, get_hierarchy,
    get_id_name_mapping, get_id_synonyms_mapping, get_name, get_name_by_curie, get_name_id_mapping, get_primary_curie,
    get_primary_identifier, get_subhierarchy, get_xrefs_df,
)
from .getters import get  # noqa: F401
from .identifier_utils import normalize_curie, normalize_prefix  # noqa: F401
from .normalizer import OboNormalizer, ground  # noqa: F401
from .path_utils import ensure_path  # noqa: F401
from .sources import CONVERTED, get_converted_obo, iter_converted_obos  # noqa: F401
from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef  # noqa: F401
from .version import get_version  # noqa: F401
from .xrefdb.xrefs_pipeline import Canonicalizer, get_equivalent, get_priority_curie  # noqa: F401
