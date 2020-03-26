# -*- coding: utf-8 -*-

"""Converter for NCI PID."""

import logging
from typing import Iterable

from ..path_utils import ensure_excel
from ..struct import Obo, Reference, Term

logger = logging.getLogger(__name__)

PREFIX = 'pid.pathway'
URL = 'https://github.com/NCIP/pathway-interaction-database/raw/master/download/NCI-Pathway-Info.xlsx'


def get_obo() -> Obo:
    """Get NCI PID as OBO."""
    return Obo(
        ontology=PREFIX,
        name='NCI Pathway Interaction Database',
        iter_terms=iter_terms,
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over NCI PID terms."""
    df = ensure_excel(PREFIX, URL)

    for identifier, name in df[['PID', 'Pathway Name']].values:
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )


if __name__ == '__main__':
    get_obo().write_default()
