# -*- coding: utf-8 -*-

"""Converter for UMLS.

Run with ``python -m pyobo.sources.umls``
"""

import itertools as itt
import operator
import os
from typing import Iterable

import bioregistry
import pandas as pd
from tqdm.auto import tqdm
from umls_downloader import open_umls

from pyobo import Obo, Reference, Synonym, SynonymTypeDef, Term
from pyobo.utils.io import open_map_tsv

__all__ = [
    "UMLSGetter",
]

HERE = os.path.abspath(os.path.dirname(__file__))
SYNONYM_TYPE_PATH = os.path.join(HERE, "synonym_types.tsv")

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

SYNONYM_ABB = open_map_tsv(SYNONYM_TYPE_PATH)


class UMLSGetter(Obo):
    """An ontology representation of UMLS."""

    ontology = bioversions_key = PREFIX
    synonym_typedefs = [SynonymTypeDef.from_text(v) for v in SYNONYM_ABB.values()]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def get_obo() -> Obo:
    """Get UMLS as OBO."""
    return UMLSGetter()


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over UMLS terms."""
    with open_umls(version=version) as file:
        it = tqdm(file, unit_scale=True, desc="[umls] parsing")
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
                SYNONYM_ABB.__getitem__
            )

            _r = pref_rows_df.iloc[0]
            sdf = df[["SAB - source name", "CODE", "TTY - Term Type in Source", "STR"]]

            synonyms = []
            xrefs = []
            for source, identifier, synonym_type, synonym in sdf.values:
                norm_source = bioregistry.normalize_prefix(source)
                if norm_source is None or not identifier:
                    provenance = []
                else:
                    ref = Reference(prefix=norm_source, identifier=identifier)
                    provenance = [ref]
                    xrefs.append(ref)
                synonyms.append(
                    Synonym(
                        name=synonym,
                        provenance=provenance,
                        type=SynonymTypeDef.from_text(synonym_type),
                    )
                )

            xrefs = sorted(
                set(xrefs), key=lambda reference: (reference.prefix, reference.identifier)
            )

            term = Term(
                reference=Reference(prefix=PREFIX, identifier=cui, name=_r["STR"]),
                synonyms=synonyms,
                xrefs=xrefs,
            )
            yield term


if __name__ == "__main__":
    UMLSGetter.cli()
