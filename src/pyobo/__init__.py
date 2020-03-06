# -*- coding: utf-8 -*-

"""A python package for handling and generating OBO."""

from .mappings import get_all_xrefs, get_synonyms, get_xrefs, iterate_xrefs_from_graph  # noqa: F401
from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef  # noqa: F401
from .utils import ensure_path, get_id_name_mapping, get_obo_graph_by_prefix, get_obo_graph_by_url  # noqa: F401
from .version import get_version  # noqa: F401
