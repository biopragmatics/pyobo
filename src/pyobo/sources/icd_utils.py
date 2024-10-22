"""Utilities or interacting with the ICD API.

Want to get your own API cliend ID and client secret?

1. Register at https://icdapihome.azurewebsites.net/icdapi/Account/Register
2. Sell your soul to the American government
"""

import datetime
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Callable, Union

import pystow
import requests
from cachier import cachier
from pystow.config_api import ConfigError
from tqdm.auto import tqdm

from ..getters import NoBuildError
from ..struct import Term

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"  # noqa:S105

ICD_BASE_URL = "https://id.who.int/icd"

ICD11_TOP_LEVEL_URL = f"{ICD_BASE_URL}/entity"
ICD10_TOP_LEVEL_URL = f"{ICD_BASE_URL}/release/10/2016"


def get_icd(url: str) -> requests.Response:
    """Get an ICD API endpoint."""
    return requests.get(url, headers=get_icd_api_headers())


def _get_entity(endpoint: str, identifier: str):
    url = f"{endpoint}/{identifier}"
    # tqdm.write(f'query {identifier} at {url}')
    res = get_icd(url)
    return res.json()


def get_child_identifiers(endpoint: str, res_json: Mapping[str, Any]) -> list[str]:
    """Ge the child identifiers."""
    return [url[len(endpoint) :].lstrip("/") for url in res_json.get("child", [])]


@cachier(stale_after=datetime.timedelta(minutes=45))
def get_icd_api_headers() -> Mapping[str, str]:
    """Get the headers, and refresh every hour."""
    try:
        icd_client_id = pystow.get_config("pyobo", "icd_client_id", raise_on_missing=True)
        icd_client_secret = pystow.get_config("pyobo", "icd_client_secret", raise_on_missing=True)
    except ConfigError as e:
        raise NoBuildError from e

    grant_type = "client_credentials"
    body_params = {"grant_type": grant_type}
    tqdm.write("getting ICD API token")
    res = requests.post(TOKEN_URL, data=body_params, auth=(icd_client_id, icd_client_secret))
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
    directory: Union[str, Path],
    *,
    endpoint: str,
    converter: Callable[[Mapping[str, Any]], Term],
) -> Iterable[Term]:
    """Iterate over all terms from the ICD endpoint."""
    path = Path(directory).joinpath(identifier).with_suffix(".json")
    if identifier in visited_identifiers:
        return
    visited_identifiers.add(identifier)

    if os.path.exists(path):
        with open(path) as file:
            res_json = json.load(file)
    else:
        res_json = _get_entity(endpoint, identifier)
        with open(path, "w") as file:
            json.dump(res_json, file, indent=2)

    yield converter(res_json)
    for identifier in get_child_identifiers(endpoint, res_json):
        yield from visiter(
            identifier,
            visited_identifiers,
            directory,
            converter=converter,
            endpoint=endpoint,
        )
