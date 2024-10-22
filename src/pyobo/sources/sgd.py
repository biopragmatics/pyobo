"""Converter for SGD."""

from collections.abc import Iterable
from urllib.parse import unquote_plus

from ..struct import Obo, Reference, Synonym, Term, from_species
from ..utils.path import ensure_tar_df

__all__ = [
    "SGDGetter",
]

HEADER = ["chromosome", "database", "feature", "start", "end", "a", "b", "c", "data"]
PREFIX = "sgd"

URL = (
    "https://downloads.yeastgenome.org/sequence/"
    "S288C_reference/genome_releases/S288C_reference_genome_R64-2-1_20150113.tgz"
)
INNER_PATH = "S288C_reference_genome_R64-2-1_20150113/saccharomyces_cerevisiae_R64-2-1_20150113.gff"


class SGDGetter(Obo):
    """An ontology representation of SGD's yeast gene nomenclature."""

    bioversions_key = ontology = PREFIX
    typedefs = [from_species]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms for SGD."""
        yield from get_terms(self, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get SGD as OBO."""
    return SGDGetter(force=force)


def get_terms(ontology: Obo, force: bool = False) -> Iterable[Term]:
    """Get SGD terms."""
    df = ensure_tar_df(
        prefix=PREFIX,
        url=URL,
        inner_path=INNER_PATH,
        sep="\t",
        skiprows=18,
        header=None,
        names=HEADER,
        force=force,
        dtype=str,
        version=ontology._version_or_raise,
    )
    df = df[df["feature"] == "gene"]
    for data in df["data"]:
        d = dict(entry.split("=") for entry in data.split(";"))

        identifier = d["dbxref"][len("SGD:") :]
        name = d["Name"]
        definition = unquote_plus(d["Note"])

        synonyms = []

        aliases = d.get("Alias")
        if aliases:
            for alias in aliases.split(","):
                synonyms.append(Synonym(name=unquote_plus(alias)))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
            synonyms=synonyms,
        )
        term.set_species(identifier="4932", name="Saccharomyces cerevisiae")
        yield term


if __name__ == "__main__":
    SGDGetter.cli()
