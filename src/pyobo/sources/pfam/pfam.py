"""Convert PFAM to OBO."""

from collections.abc import Iterable

import pandas as pd

from ...struct import Obo, Reference, Term
from ...utils.path import ensure_df

__all__ = [
    "PfamGetter",
]

PREFIX = "pfam"

CLAN_MAPPING_HEADER = [
    "family_id",
    "clan_id",
    "clan_name",
    "family_name",
    "family_summary",
]


def get_pfam_clan_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get PFAM + clans."""
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam{version}/Pfam-A.clans.tsv.gz"
    return ensure_df(
        PREFIX,
        url=url,
        compression="gzip",
        names=CLAN_MAPPING_HEADER,
        version=version,
        dtype=str,
        force=force,
        backend="urllib",
    )


class PfamGetter(Obo):
    """An ontology representation of Pfam's protein family nomenclature."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(self._version_or_raise, force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate PFAM terms."""
    df = get_pfam_clan_df(version=version, force=force)
    for family_identifier, clan_id, clan_name, family_name, definition in df.values:
        parents = []
        if pd.notna(clan_id) and pd.notna(clan_name):
            parents.append(Reference(prefix="pfam.clan", identifier=clan_id, name=clan_name))
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=family_identifier, name=family_name),
            definition=definition,
            parents=parents,
        )


if __name__ == "__main__":
    PfamGetter.cli()
