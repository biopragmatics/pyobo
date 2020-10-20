# -*- coding: utf-8 -*-

"""Convert DrugBank Salts to OBO.

Run with ``python -m pyobo.sources.drugbank_salt``
"""

import logging
from typing import Iterable

from .drugbank import iterate_drug_info
from ..struct import Obo, Reference, Term

logger = logging.getLogger(__name__)

PREFIX = 'drugbank.salt'


def get_obo() -> Obo:
    """Get DrugBank Salts as OBO."""
    return Obo(
        ontology=PREFIX,
        name='DrugBank Salts',
        iter_terms=iter_terms,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over DrugBank Salt terms in OBO."""
    for drug_info in iterate_drug_info():
        for salt in drug_info.get('salts', []):
            xrefs = []
            for key in ['unii', 'cas_id', 'inchikey']:
                identifier = salt.get(key)
                if identifier is not None:
                    xrefs.append(Reference(prefix=key, identifier=identifier))

            yield Term(
                reference=Reference(
                    prefix=PREFIX,
                    identifier=salt['identifier'],
                    name=salt['name'],
                ),
                xrefs=xrefs,
            )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    get_obo().write_default()
