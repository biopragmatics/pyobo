# -*- coding: utf-8 -*-

"""Sources of OBO content."""

import os
from importlib import import_module
from typing import Iterable

from ..struct import Obo

__all__ = [
    'CONVERTED',
    'get_converted_obo',
    'iter_converted_obos',
]

HERE = os.path.abspath(os.path.dirname(__file__))

CONVERTED = {
    'cgnc': 'cgnc',
    'complexportal': 'complexportal',
    'ncbigene': 'ncbigene',
    'ec-code': 'expasy',
    'hgnc': 'hgnc',
    'hgnc.genefamily': 'hgncgenefamily',
    'mesh': 'mesh',
    'mgi': 'mgi',
    'msig': 'msig',
    'mirbase': 'mirbase',
    'pathbank': 'pathbank',
    'pid.pathway': 'pid',
    'pubchem.compound': 'pubchem',
    'reactome': 'reactome',
    'rgd': 'rgd',
    'sgd': 'sgd',
    'wikipathways': 'wikipathways',
}


def get_converted_obo(prefix: str) -> Obo:
    """Get a converted PyOBO source."""
    module = import_module(f'pyobo.sources.{CONVERTED[prefix]}')
    return module.get_obo()


def iter_converted_obos() -> Iterable[Obo]:
    """Get all modules in the PyOBO sources."""
    for prefix in sorted(CONVERTED):
        yield get_converted_obo(prefix)
