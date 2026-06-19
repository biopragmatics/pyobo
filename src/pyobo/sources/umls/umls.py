"""Converter for UMLS.

Run with ``python -m pyobo.sources.umls``
"""

import itertools as itt
import operator
from collections import defaultdict
from collections.abc import Iterable, Mapping

import bioregistry
import pandas as pd
from tqdm.auto import tqdm
from umls_downloader import (
    open_mrconso_dict_reader,
    open_umls_semantic_types,
)

from pyobo import Obo, Reference, Synonym, SynonymTypeDef, Term
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
        lines = tqdm(reader, unit_scale=True, desc="[umls] parsing", total=LENGTH)
        lines = (
            line
            for line in lines
            # only keep english language for now
            if line["LAT - Language"] == "ENG"
        )
        for cui, cui_lines_it in itt.groupby(lines, key=operator.itemgetter(0)):
            cui_lines = list(cui_lines_it)
            preferred_lines = [
                line
                for line in cui_lines
                if line["ISPREF - is preferred"] == "Y"
                and line["TS - Term Status"] == "P"
                and line["STT - String Type"] == "PF"
            ]
            if len(preferred_lines) != 1:
                # it.write(f"no preferred term for umls:{cui}. got {len(pref_rows_df.index)}")
                continue
            preferred_line = preferred_lines[0]

            term = Term.from_triple(prefix=PREFIX, identifier=cui, name=preferred_line["STR"])

            sdf = df[
                [
                    "SAB - source name",
                    "CODE",
                    "TTY - Term Type in Source",
                    "STR",
                ]
            ]

            for source, identifier, synonym_type, synonym in sdf.values:
                norm_source = bioregistry.normalize_prefix(source)
                if not norm_source or not identifier or "," in identifier:
                    provenance = []
                else:
                    try:
                        ref = Reference(prefix=norm_source, identifier=identifier)
                    except ValueError:
                        continue
                    else:
                        provenance = [ref]
                        xrefs.add(ref)
                synonyms.append(
                    Synonym(
                        name=synonym,
                        provenance=provenance,
                        type=UMLS_TYPEDEFS[synonym_type].reference,
                    )
                )


            for sty_id in semantic_types.get(cui, set()):
                term.append_parent(Reference(prefix="sty", identifier=sty_id))
            yield term


if __name__ == "__main__":
    for _ in zip(range(10_000), iter_terms("2025AB"), strict=False):
        pass
