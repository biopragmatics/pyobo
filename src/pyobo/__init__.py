# -*- coding: utf-8 -*-

"""A python package for handling and generating OBO."""

from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef  # noqa: F401
from .utils import get_id_name_mapping, get_obo_graph, get_obo_graph_by_url  # noqa: F401
from .version import get_version  # noqa: F401
