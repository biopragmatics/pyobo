# -*- coding: utf-8 -*-

from .utils import build_term_getter

__all__ = [
    'CHEBI_OBO_URL',
    'get_chebi_terms',
]

CHEBI_OBO_URL = 'http://purl.obolibrary.org/obo/chebi.obo'
get_chebi_terms = build_term_getter(CHEBI_OBO_URL)
