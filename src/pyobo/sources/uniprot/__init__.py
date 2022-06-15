# -*- coding: utf-8 -*-

"""Converters for UniProt resources."""

from .uniprot import UniProtGetter
from .uniprot_ptm import UniProtPtmGetter

__all__ = [
    "UniProtGetter",
    "UniProtPtmGetter",
]
