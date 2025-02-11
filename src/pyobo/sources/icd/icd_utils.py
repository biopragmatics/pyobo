"""Utilities or interacting with the ICD API.

Want to get your own API client ID and client secret?

1. Register at https://icdapihome.azurewebsites.net/icdapi/Account/Register
2. Sell your soul to the American government

.. note::

    If web requests are stalling, try deleting the ``~/.cachier`` directory.
"""

import datetime
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import pystow
import requests
from cachier import cachier
from pystow.config_api import ConfigError
from tqdm.auto import tqdm

from ...getters import NoBuildError
from ...struct import Term

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"  # noqa:S105

ICD_BASE_URL = "https://id.who.int/icd"

ICD11_TOP_LEVEL_URL = f"{ICD_BASE_URL}/entity"
ICD_11_MMS_URL = f"{ICD_BASE_URL}/release/11/2024-01/mms"
ICD10_TOP_LEVEL_URL = f"{ICD_BASE_URL}/release/10/2016"


def get_icd(url: str) -> requests.Response:
    """Get an ICD API endpoint."""
    headers = get_icd_api_headers()
    return requests.get(url, headers=headers, timeout=5)


def get_icd_10_top(version: str, path: Path) -> dict[str, Any]:
    """Get from the ICD10 top."""
    if path.is_file():
        return json.loads(path.read_text())
    rv = get_icd(ICD10_TOP_LEVEL_URL).json()
    path.write_text(json.dumps(rv, indent=2))
    return rv


def get_icd_11(identifier: str) -> dict[str, Any]:
    """Get from ICD11."""
    return get_icd_entity(ICD11_TOP_LEVEL_URL, identifier)


def get_icd_11_mms(identifier: str) -> dict[str, Any]:
    """Get from ICD11 MMS."""
    return get_icd_entity(ICD_11_MMS_URL, identifier)


class ICDError(ValueError):
    """An error on getting data from ICD."""

    def __init__(self, identifier: str, url: str, text: str) -> None:
        """Instantiate an ICD error."""
        self.identifier = identifier
        self.url = url
        self.text = text

    def __str__(self) -> str:
        """Make a string for the ICD error."""
        return f"[icd11:{self.identifier}] Error getting {self.url} - {self.text}. Try {ICD11_TOP_LEVEL_URL}/{self.identifier}"


def get_icd_entity(endpoint: str, identifier: str) -> dict[str, Any]:
    """Query a given endpoint at ICD."""
    url = f"{endpoint}/{identifier}"
    res = get_icd(url)
    try:
        rv = res.json()
    except OSError:
        raise ICDError(identifier, url, res.text) from None
    return rv


def get_child_identifiers(endpoint: str, res_json: Mapping[str, Any]) -> list[str]:
    """Ge the child identifiers."""
    return [url[len(endpoint) :].lstrip("/") for url in res_json.get("child", [])]


DELAY = 45


@cachier(stale_after=datetime.timedelta(minutes=DELAY))
def get_icd_api_headers() -> Mapping[str, str]:
    """Get the headers, and refresh every hour."""
    tqdm.write("Getting ICD credentials w/ PyStow")
    try:
        icd_client_id = pystow.get_config("pyobo", "icd_client_id", raise_on_missing=True)
        icd_client_secret = pystow.get_config("pyobo", "icd_client_secret", raise_on_missing=True)
    except ConfigError as e:
        raise NoBuildError from e

    grant_type = "client_credentials"
    body_params = {"grant_type": grant_type}
    tqdm.write(f"getting ICD API token, good for {DELAY} minutes")
    res = requests.post(
        TOKEN_URL, data=body_params, auth=(icd_client_id, icd_client_secret), timeout=10
    )
    res_json = res.json()
    access_type = res_json["token_type"]
    access_token = res_json["access_token"]
    return {
        "API-Version": "v2",
        "Accept-Language": "en",
        "Authorization": f"{access_type} {access_token}",
    }


def visiter(
    identifier: str,
    visited_identifiers: set[str],
    directory: str | Path,
    *,
    endpoint: str,
    converter: Callable[[Mapping[str, Any]], Term],
) -> Iterable[Term]:
    """Iterate over all terms from the ICD endpoint."""
    path = Path(directory).joinpath(identifier).with_suffix(".json")
    if identifier in visited_identifiers:
        return
    visited_identifiers.add(identifier)

    if path.is_file():
        res_json = json.loads(path.read_text())
    else:
        res_json = get_icd_entity(endpoint, identifier)
        path.write_text(json.dumps(res_json, indent=2))

    yield converter(res_json)
    for identifier in get_child_identifiers(endpoint, res_json):
        yield from visiter(
            identifier,
            visited_identifiers,
            directory,
            converter=converter,
            endpoint=endpoint,
        )
