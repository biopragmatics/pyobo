# -*- coding: utf-8 -*-

"""Converter for UMLS.

Run with ``python -m pyobo.sources.umls``
"""

import itertools as itt
import operator
import os
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
from tqdm import tqdm

from pyobo import Obo, Reference, Synonym, SynonymTypeDef, Term, normalize_prefix
from pyobo.constants import RAW_MODULE
from pyobo.utils.io import open_map_tsv
from pyobo.utils.path import ensure_path

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


def _get_version() -> str:
    return "2020AB"


SYNONYM_ABB = open_map_tsv(SYNONYM_TYPE_PATH)


class UMLSGetter(Obo):
    ontology = PREFIX
    synonym_typedefs = [SynonymTypeDef.from_text(v) for v in SYNONYM_ABB.values()]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        return iter_terms(_get_version())


def get_obo() -> Obo:
    """Get UMLS as OBO."""
    return UMLSGetter()


def iter_terms(version: str, autodownload: bool = False) -> Iterable[Term]:
    """Iterate over UMLS terms."""
    name = f"umls-{version}-mrconso.zip"
    url = f"https://download.nlm.nih.gov/umls/kss/{version}/{name}"
    if autodownload:
        # FIXME needs automated scrapy step where you put in user/password
        path = Path(ensure_path(PREFIX, url=url, version=version))
    else:
        path = RAW_MODULE.get(PREFIX, version, name=name)
        if not path.exists():
            raise FileNotFoundError(
                f"UMLS needs to be downloaded manually still and moved to  {path}. "
                f"See https://www.nlm.nih.gov/research/umls/index.html",
            )

    with zipfile.ZipFile(path) as zip_file:
        with zip_file.open("MRCONSO.RRF", mode="r") as file:
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
                    it.write(f"no preferred term for umls:{cui}. got {len(pref_rows_df.index)}")
                    continue

                df["TTY - Term Type in Source"] = df["TTY - Term Type in Source"].map(
                    SYNONYM_ABB.__getitem__
                )

                _r = pref_rows_df.iloc[0]
                sdf = df[["SAB - source name", "CODE", "TTY - Term Type in Source", "STR"]]

                synonyms = []
                xrefs = []
                for source, identifier, synonym_type, synonym in sdf.values:
                    norm_source = normalize_prefix(source)
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
    UMLSGetter.cls_cli()
