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
    'chembl.compound': 'chembl',
    'complexportal': 'complexportal',
    'conso': 'conso',
    'covid': 'covid',
    'drugbank': 'drugbank',
    'eccode': 'expasy',
    'hgnc': 'hgnc',
    'hgnc.genefamily': 'hgncgenefamily',
    'interpro': 'interpro',
    'itis': 'itis',
    'mesh': 'mesh',
    'mgi': 'mgi',
    'mirbase': 'mirbase',
    'mirbase.family': 'mirbase_family',
    'mirbase.mature': 'mirbase_mature',
    'msig': 'msig',
    'ncbigene': 'ncbigene',
    'npass': 'npass',
    'pathbank': 'pathbank',
    'pfam': 'pfam',
    'pfam.clan': 'pfam_clan',
    'pid.pathway': 'pid',
    'pubchem.compound': 'pubchem',
    'reactome': 'reactome',
    'rgd': 'rgd',
    'sgd': 'sgd',
    'umls': 'umls',
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
