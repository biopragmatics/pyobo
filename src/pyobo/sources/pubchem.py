# -*- coding: utf-8 -*-

"""Converter for PubChem Compound."""

import logging
from typing import Iterable

from tqdm import tqdm

from ..iter_utils import iterate_gzips_together
from ..path_utils import ensure_path
from ..struct import Obo, Reference, Synonym, Term

logger = logging.getLogger(__name__)

PREFIX = 'pubchem.compound'
VERSION = '2020-03-01'
BASE_URL = f'ftp://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Monthly/{VERSION}/Extras'

# 2 tab-separated columns: compound_id, name
CID_NAME_URL = f'{BASE_URL}/CID-Title.gz'
# 2 tab-separated columns: compound_id, synonym
CID_SYNONYMS_URL = f'{BASE_URL}/CID-Synonym-filtered.gz'

# TODO
CID_PMID_URL = f'{BASE_URL}/CID-PMID.gz'


def get_obo() -> Obo:
    """Get PubChem Compound OBO."""
    obo = Obo(
        ontology='pubchem.compound',
        name='PubChem Compound',
        iter_terms=get_terms,
        data_version=VERSION,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )
    return obo


def get_terms(use_tqdm: bool = True) -> Iterable[Term]:
    """Get PubChem Compound terms."""
    cid_name_path = ensure_path(PREFIX, CID_NAME_URL, version=VERSION)
    cid_synonyms_path = ensure_path(PREFIX, CID_SYNONYMS_URL, version=VERSION)

    it = iterate_gzips_together(cid_name_path, cid_synonyms_path)

    if use_tqdm:
        total = 146000000  # got this by reading the exports page
        it = tqdm(it, desc=f'mapping {PREFIX}', unit_scale=True, unit='compound', total=total)
    for identifier, name, raw_synonyms in it:
        reference = Reference(prefix=PREFIX, identifier=identifier, name=name)
        xrefs = []
        synonyms = []
        for synonym in raw_synonyms:
            if synonym.startswith('CHEBI:'):
                xrefs.append(Reference(prefix='chebi', identifier=synonym))
            elif synonym.startswith('CHEMBL'):
                xrefs.append(Reference(prefix='chembl', identifier=synonym))
            elif synonym.startswith('InChI='):
                xrefs.append(Reference(prefix='inchi', identifier=synonym))
            elif synonym.startswith('SCHEMBL'):
                xrefs.append(Reference(prefix='schembl', identifier=synonym))
            else:
                synonyms.append(Synonym(name=synonym))
            # TODO check other xrefs

        term = Term(
            reference=reference,
            synonyms=synonyms,
            xrefs=xrefs,
        )
        yield term


if __name__ == '__main__':
    get_obo().write_default()
