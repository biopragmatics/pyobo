# -*- coding: utf-8 -*-

"""Convert PFAM Clans to OBO."""

from typing import Iterable

from tqdm import tqdm

from .pfam import get_pfam_clan_df
from ..struct import Obo, Reference, Term

PREFIX = 'pfam.clan'


def get_obo() -> Obo:
    """Get PFAM Clans as OBO."""
    return Obo(
        ontology=PREFIX,
        name='PFAM Clans',
        iter_terms=iter_terms,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


# TODO could get definitions from ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam33.0/Pfam-C.gz

def iter_terms() -> Iterable[Term]:
    """Iterate PFAM clan terms."""
    df = get_pfam_clan_df()
    df = df[['clan_id', 'clan_name']].drop_duplicates()
    it = tqdm(df.values, total=len(df.index), desc=f'mapping {PREFIX}')
    for identifier, name in it:
        yield Term(
            reference=Reference(PREFIX, identifier=identifier, name=name),
        )


if __name__ == '__main__':
    get_obo().write_default()
