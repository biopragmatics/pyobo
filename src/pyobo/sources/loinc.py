"""Convert LOINC to OBO."""

import datetime
from pathlib import Path

import pystow
import requests
from pydantic import BaseModel, Field


class Status(BaseModel):
    """Status from polling the endpoint."""

    version: str
    release_date: datetime.datetime = Field(..., alias="releaseDate")
    relma_version: str = Field(..., alias="relmaVersion")
    count: int = Field(..., alias="numberOfLoincs")
    max_loinc: str = Field(..., alias="maxLoinc")
    download_url: str = Field(..., alias="downloadUrl")
    download_mdf_hash: str = Field(..., alias="downloadMD5Hash")


def ensure_loinc(user: str | None = None, password: str | None = None) -> tuple[Status, Path]:
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
        download_kwargs={
            "backend": "requests",
            "auth": auth,
        },
    )
    return status, path
