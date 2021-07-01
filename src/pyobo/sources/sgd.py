# -*- coding: utf-8 -*-

"""Converter for SGD."""

from typing import Iterable
from urllib.parse import unquote_plus

from ..struct import Obo, Reference, Synonym, SynonymTypeDef, Term, from_species
from ..utils.path import ensure_tar_df

HEADER = ["chromosome", "database", "feature", "start", "end", "a", "b", "c", "data"]
PREFIX = "sgd"

URL = (
    "https://downloads.yeastgenome.org/sequence/"
    "S288C_reference/genome_releases/S288C_reference_genome_R64-2-1_20150113.tgz"
)
INNER_PATH = "S288C_reference_genome_R64-2-1_20150113/saccharomyces_cerevisiae_R64-2-1_20150113.gff"

alias_type = SynonymTypeDef(id="alias", name="alias")


def get_obo() -> Obo:
    """Get SGD as OBO."""
    return Obo(
        ontology=PREFIX,
        name="Saccharomyces Genome Database",
        iter_terms=get_terms,
        typedefs=[from_species],
        synonym_typedefs=[alias_type],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_terms() -> Iterable[Term]:
    """Get SGD terms."""
    df = ensure_tar_df(
        prefix=PREFIX,
        url=URL,
        inner_path=INNER_PATH,
        sep="\t",
        skiprows=18,
        header=None,
        names=HEADER,
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
                synonyms.append(Synonym(name=unquote_plus(alias), type=alias_type))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
            synonyms=synonyms,
        )
        term.set_species(identifier="4932", name="Saccharomyces cerevisiae")
        yield term


if __name__ == "__main__":
    get_obo().write_default()
