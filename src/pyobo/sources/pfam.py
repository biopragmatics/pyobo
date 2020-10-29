# -*- coding: utf-8 -*-

"""Convert PFAM to OBO."""

from typing import Iterable

import pandas as pd
from tqdm import tqdm

from ..path_utils import ensure_df
from ..struct import Obo, Reference, Term

PREFIX = 'pfam'

VERSION = '33.0'
CLAN_MAPPING_URL = f'ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam{VERSION}/Pfam-A.clans.tsv.gz'
CLAN_MAPPING_HEADER = [
    'family_id',
    'clan_id',
    'clan_name',
    'family_name',
    'family_summary',
]


def get_pfam_clan_df() -> pd.DataFrame:
    """Get PFAM + clans."""
    return ensure_df(
        PREFIX,
        CLAN_MAPPING_URL,
        compression='gzip',
        names=CLAN_MAPPING_HEADER,
        version=VERSION,
        dtype=str,
    )


def get_obo() -> Obo:
    """Get PFAM as OBO."""
    return Obo(
        ontology=PREFIX,
        name='PFAM',
        iter_terms=iter_terms,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def iter_terms() -> Iterable[Term]:
    """Iterate PFAM  terms."""
    df = get_pfam_clan_df()
    it = tqdm(df.values, total=len(df.index), desc=f'mapping {PREFIX}')
    for family_identifier, clan_id, clan_name, family_name, definition in it:
        parents = []
        if pd.notna(clan_id) and pd.notna(clan_name):
            parents.append(Reference('pfam.clan', identifier=clan_id, name=clan_name))
        yield Term(
            reference=Reference(PREFIX, identifier=family_identifier, name=family_name),
            definition=definition,
            parents=parents,
        )


if __name__ == '__main__':
    get_obo().write_default()
