"""Converters for UniProt resources."""

from .uniprot import PREFIX, UniProtGetter
from .uniprot_ptm import UniProtPtmGetter

__all__ = [
    "UniProtGetter",
    "UniProtPtmGetter",
    "PREFIX",
]
