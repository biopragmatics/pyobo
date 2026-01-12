"""Convert LOINC to OBO."""

import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import pystow
import requests
from pydantic import BaseModel, Field
from pystow.utils import read_zipfile_csv

from pyobo import Obo, Reference, Term

PREFIX = "loinc"


class LOINCGetter(Obo):
    """An ontology representation of LOINC."""

    bioversions_key = ontology = PREFIX
    typedefs = []
    root_terms = []

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for LOINC."""
        yield from get_terms()


def get_terms(*, force: bool = False) -> Iterable[Term]:
    """Get terms."""
    _status, path = ensure_loinc(force=force)
    df = read_zipfile_csv(path, inner_path="LoincTable/Loinc.csv", sep=",")
    for _, row in df.iterrows():
        yield get_term(row)


def get_term(row: dict[str, Any]) -> Term:
    """Get a term for a row in the LOINC table."""
    reference = Reference(prefix=PREFIX, identifier=row["LOINC_NUM"], name=row.get("COMPONENT"))
    term = Term(
        reference=reference,
        definition=definition if pd.notna(definition := row.get("DefinitionDescription")) else None,
    )
    if pd.notna(short_name := row.get("SHORTNAME")):
        term.append_synonym(short_name)
    if pd.notna(long_common_name := row.get("LONG_COMMON_NAME")):
        term.append_synonym(long_common_name)

    return term


class Status(BaseModel):
    """Status from polling the endpoint."""

    version: str
    release_date: datetime.datetime = Field(..., alias="releaseDate")
    relma_version: str = Field(..., alias="relmaVersion")
    count: int = Field(..., alias="numberOfLoincs")
    max_loinc: str = Field(..., alias="maxLoinc")
    download_url: str = Field(..., alias="downloadUrl")
    download_mdf_hash: str = Field(..., alias="downloadMD5Hash")


def ensure_loinc(
    *, user: str | None = None, password: str | None = None, force: bool = False
) -> tuple[Status, Path]:
    """Get the latest data from LOINC."""
    user = pystow.get_config("loinc", "user", passthrough=user, raise_on_missing=True)
    password = pystow.get_config("loinc", "password", passthrough=password, raise_on_missing=True)
    auth = (user, password)
    response = requests.get("https://loinc.regenstrief.org/api/v1/Loinc", auth=auth)
    status = Status.model_validate(response.json())
    path = pystow.ensure(
        "loinc",
        version=status.version,
        url=status.download_url,
        name=f"{status.version}.zip",
        force=force,
        download_kwargs={
            "backend": "requests",
            "auth": auth,
        },
    )
    return status, path


if __name__ == "__main__":
    LOINCGetter.cli()
