# -*- coding: utf-8 -*-

"""Convert ICD-10 to OBO."""

from typing import Iterable

from pyobo.struct import Obo, Term

PREFIX = 'icd10'
VERSION = '2016'


def get_obo() -> Obo:
    """Get ICD-10 as OBO."""
    return Obo(
        ontology=PREFIX,
        name='International Statistical Classification of Diseases and Related Health Problems 10th Revision',
        auto_generated_by=f'bio2obo:{PREFIX}',
        iter_terms=iter_terms,
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over ICD-10 terms."""
