"""Convert PFAM Clans to OBO."""

from collections.abc import Iterable

from tqdm.auto import tqdm

from .pfam import get_pfam_clan_df
from ..struct import Obo, Reference, Term

__all__ = [
    "PfamClanGetter",
]

PREFIX = "pfam.clan"


class PfamClanGetter(Obo):
    """An ontology representation of Pfam's protein clan nomenclature."""

    ontology = PREFIX
    bioversions_key = "pfam"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get PFAM Clans as OBO."""
    return PfamClanGetter(force=force)


# TODO could get definitions from ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam33.0/Pfam-C.gz


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate PFAM clan terms."""
    df = get_pfam_clan_df(version=version, force=force)
    df = df[df["clan_id"].notna()]
    df = df[["clan_id", "clan_name"]].drop_duplicates()
    it = tqdm(df.values, total=len(df.index), desc=f"mapping {PREFIX}")
    for identifier, name in it:
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )


if __name__ == "__main__":
    get_obo().write_default()
