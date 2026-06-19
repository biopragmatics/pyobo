"""Converter for UMLS.

Run with ``python -m pyobo.sources.umls``
"""

import itertools as itt
import operator
from collections import defaultdict
from collections.abc import Iterable, Mapping

import bioregistry
from tqdm.auto import tqdm
from umls_downloader import open_mrconso_dict_reader, open_umls_semantic_types

from pyobo import Obo, Reference, SynonymTypeDef, Term
from pyobo.sources.umls.get_synonym_types import get_umls_typedefs

__all__ = [
    "UMLSGetter",
]

PREFIX = "umls"
SOURCE_VOCAB_URL = "https://www.nlm.nih.gov/research/umls/sourcereleasedocs/index.html"
UMLS_TYPEDEFS: dict[str, SynonymTypeDef] = get_umls_typedefs()


class UMLSGetter(Obo):
    """An ontology representation of UMLS."""

    ontology = bioversions_key = PREFIX
    synonym_typedefs = list(UMLS_TYPEDEFS.values())

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def get_semantic_types(*, version: str | None = None) -> Mapping[str, set[str]]:
    """Get UMLS semantic types for each term."""
    dd = defaultdict(set)
    with open_umls_semantic_types(version=version) as file:
        # this is very fast and doesn't need a progress bar
        for line in file:
            cui, sty, _ = line.decode("utf8").split("|", 2)
            dd[cui].add(sty)
    return dict(dd)


LENGTH = 17_500_000


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over UMLS terms."""
    semantic_types = get_semantic_types(version=version)
    with open_mrconso_dict_reader(version=version) as reader:
        lines: Iterable[Mapping[str, str]] = tqdm(
            reader, unit_scale=True, desc=f"[{PREFIX}] parsing", total=LENGTH
        )
        lines = (
            line
            for line in lines
            # only keep english language for now
            if line["LAT - Language"] == "ENG"
        )
        # could multiprocess after grouping?
        for cui, cui_lines_it in itt.groupby(lines, key=operator.itemgetter("CUI")):
            term = _get_term(cui, cui_lines_it, semantic_types)
            if term is not None:
                yield term


def _get_term(
    cui: str, cui_lines_it: Iterable[Mapping[str, str]], semantic_types: Mapping[str, set[str]]
) -> Term | None:
    cui_lines = list(cui_lines_it)
    preferred_lines = [
        cui_line
        for cui_line in cui_lines
        if cui_line["ISPREF - is preferred"] == "Y"
        and cui_line["TS - Term Status"] == "P"
        and cui_line["STT - String Type"] == "PF"
    ]
    if len(preferred_lines) != 1:
        # it.write(f"no preferred term for umls:{cui}. got {len(pref_rows_df.index)}")
        return None
    preferred_line = preferred_lines[0]

    term = Term.from_triple(prefix=PREFIX, identifier=cui, name=preferred_line["STR"])

    for row in cui_lines:  # TODO this adds a duplicate for the preferred line
        xref_prefix = bioregistry.normalize_prefix(row["SAB - source name"])
        xref_identifier = row["CODE"]
        provenance: list[Reference]
        if not xref_prefix or not xref_identifier:
            provenance = []
        elif "," in xref_identifier:
            provenance = []  # TODO handle this?
        else:
            try:
                ref = Reference(prefix=xref_prefix, identifier=xref_identifier)
            except ValueError:
                continue
            else:
                provenance = [ref]
                term.append_xref(ref)
        term.append_synonym(
            row["STR"],
            provenance=provenance,
            type=UMLS_TYPEDEFS[row["TTY - Term Type in Source"]].reference,
        )

    for sty_id in semantic_types.get(cui, ()):
        term.append_parent(Reference(prefix="sty", identifier=sty_id))
    return term


if __name__ == "__main__":
    UMLSGetter.cli()
