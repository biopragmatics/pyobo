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
from umls_downloader import open_umls, open_umls_semantic_types

from pyobo import Obo, Reference, Synonym, SynonymTypeDef, Term

from .get_synonym_types import get_umls_typedefs

__all__ = [
    "UMLSGetter",
]


RRF_COLUMNS = [
    "CUI",
    "LAT - Language",
    "TS - Term Status",
    "LUI - Local Unique Identifier",
    "STT - String Type",
    "SUI - Unique Identifier for String",
    "ISPREF - is preferred",
    "AUI - Unique atom identifier",
    "SAUI - Source atom identifier",
    "SCUI - Source concept identifier",
    "SDUI - Source descriptor identifier",
    "SAB - source name",
    "TTY - Term Type in Source",
    "CODE",
    "STR",
    "SRL",
    "SUPPRESS",
    "CVF",
    "?",
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


def get_semantic_types() -> Mapping[str, set[str]]:
    """Get UMLS semantic types for each term."""
    dd = defaultdict(set)
    with open_umls_semantic_types() as file:
        # this is very fast and doesn't need a progress bar
        for line in file:
            cui, sty, _ = line.decode("utf8").split("|", 2)
            dd[cui].add(sty)
    return dict(dd)


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over UMLS terms."""
    semantic_types = get_semantic_types()

    with open_umls(version=version) as file:
        it = tqdm(file, unit_scale=True, desc="[umls] parsing", total=16_700_000)
        lines = (line.decode("utf-8").strip().split("|") for line in it)
        for cui, cui_lines in itt.groupby(lines, key=operator.itemgetter(0)):
            df = pd.DataFrame(list(cui_lines), columns=RRF_COLUMNS)
            df = df[df["LAT - Language"] == "ENG"]
            idx = (
                (df["ISPREF - is preferred"] == "Y")
                & (df["TS - Term Status"] == "P")
                & (df["STT - String Type"] == "PF"),
            )
            pref_rows_df = df.loc[idx]
            if len(pref_rows_df.index) != 1:
                # it.write(f"no preferred term for umls:{cui}. got {len(pref_rows_df.index)}")
                continue

            df["TTY - Term Type in Source"] = df["TTY - Term Type in Source"].map(
                UMLS_TYPEDEFS.__getitem__
            )

            _r = pref_rows_df.iloc[0]
            sdf = df[["SAB - source name", "CODE", "TTY - Term Type in Source", "STR"]]

            synonyms = []
            xrefs = set()
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
                        type=synonym_type.reference,
                    )
                )

            term = Term(
                reference=Reference(prefix=PREFIX, identifier=cui, name=_r["STR"]),
                synonyms=synonyms,
                xrefs=sorted(xrefs),
            )
            for sty_id in semantic_types.get(cui, set()):
                term.append_parent(Reference(prefix="sty", identifier=sty_id))
            yield term


if __name__ == "__main__":
    UMLSGetter.cli()
