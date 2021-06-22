# -*- coding: utf-8 -*-

"""Convert PFAM to OBO."""

from typing import Iterable

import bioversions
import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Term
from ..utils.path import ensure_df

PREFIX = "pfam"

CLAN_MAPPING_HEADER = [
    "family_id",
    "clan_id",
    "clan_name",
    "family_name",
    "family_summary",
]


def get_pfam_clan_df(version: str) -> pd.DataFrame:
    """Get PFAM + clans."""
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam{version}/Pfam-A.clans.tsv.gz"
    return ensure_df(
        PREFIX,
        url=url,
        compression="gzip",
        names=CLAN_MAPPING_HEADER,
        version=version,
        dtype=str,
    )


def get_obo() -> Obo:
    """Get PFAM as OBO."""
    version = bioversions.get_version("pfam")
    return Obo(
        ontology=PREFIX,
        name="PFAM",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate PFAM terms."""
    df = get_pfam_clan_df(version=version)
    it = tqdm(df.values, total=len(df.index), desc=f"mapping {PREFIX}")
    for family_identifier, clan_id, clan_name, family_name, definition in it:
        parents = []
        if pd.notna(clan_id) and pd.notna(clan_name):
            parents.append(Reference("pfam.clan", identifier=clan_id, name=clan_name))
        yield Term(
            reference=Reference(PREFIX, identifier=family_identifier, name=family_name),
            definition=definition,
            parents=parents,
        )


if __name__ == "__main__":
    get_obo().write_default()
