# -*- coding: utf-8 -*-

"""A python package for handling and generating OBO."""

from .getters import get_obo_graph, get_obo_graph_by_prefix, get_obo_graph_by_url  # noqa: F401
from .mappings.extract_names import get_id_name_mapping, get_name_id_mapping  # noqa: F401
from .mappings.extract_synonyms import get_synonyms  # noqa: F401
from .mappings.extract_xrefs import get_all_xrefs, get_xrefs, iterate_xrefs_from_graph  # noqa: F401
from .path_utils import ensure_path  # noqa: F401
from .sources import CONVERTED, get_converted_obo, get_converted_obos  # noqa: F401
from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef, get_terms_from_graph  # noqa: F401
from .version import get_version  # noqa: F401
