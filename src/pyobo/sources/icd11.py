# -*- coding: utf-8 -*-

"""Converter for ICD."""

import datetime
import json
import logging
import os
from typing import Any, Iterable, List, Mapping, Set

import click
import requests
from cachier import cachier
from tqdm import tqdm

from pyobo import Synonym
from pyobo.cli_utils import verbose_option
from pyobo.path_utils import get_prefix_directory
from pyobo.sources.icd_utils import CLIENT_ID, CLIENT_SECRET, ICD11_TOP_LEVEL_URL, TOKEN_URL
from pyobo.struct import Obo, Reference, Term

logger = logging.getLogger(__name__)

PREFIX = 'icd11'


def get_obo() -> Obo:
    """Get ICD11 as OBO."""
    return Obo(
        ontology=PREFIX,
        name='ICD-11',
        iter_terms=iterate_icd11,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


@cachier(stale_after=datetime.timedelta(hours=1))
def get_icd_api_headers() -> Mapping[str, str]:
    """Get the headers, and refresh every hour."""
    grant_type = 'client_credentials'
    body_params = {'grant_type': grant_type}
    tqdm.write('getting ICD API token')
    res = requests.post(TOKEN_URL, data=body_params, auth=(CLIENT_ID, CLIENT_SECRET))
    res_json = res.json()
    access_type = res_json['token_type']
    access_token = res_json['access_token']
    return {
        'API-Version': 'v2',
        'Accept-Language': 'en',
        'Authorization': f'{access_type} {access_token}',
    }


def iterate_icd11() -> Iterable[Term]:
    """Iterate over the terms in ICD11.

    The API doesn't seem to have a rate limit, but returns pretty slow.
    This means that it only gets results at at about 5 calls/second.
    Get ready to be patient - the API token expires every hour so there's
    a caching mechanism with :mod:`cachier` that gets a new one every hour.
    """
    res = requests.get(ICD11_TOP_LEVEL_URL, headers=get_icd_api_headers())
    res_json = res.json()

    version = res_json['releaseId']
    directory = get_prefix_directory(PREFIX, version=version)

    with open(os.path.join(directory, 'top.json'), 'w') as file:
        json.dump(res_json, file, indent=2)

    tqdm.write(f'There are {len(res_json["child"])} top level entities')

    visited_identifiers = set()
    for identifier in _get_child_identifiers(res_json):
        yield from _visit(identifier, visited_identifiers, directory)


def _get_entity(identifier: str):
    url = f'{ICD11_TOP_LEVEL_URL}/{identifier}'
    #  tqdm.write(f'query {identifier} at {url}')
    res = requests.get(url, headers=get_icd_api_headers())
    return res.json()


def _get_child_identifiers(res_json: Mapping[str, Any]) -> List[str]:
    return [
        url[len(ICD11_TOP_LEVEL_URL):].lstrip('/')
        for url in res_json.get('child', [])
    ]


def _visit(
    identifier: str,
    visited_identifiers: Set[str],
    directory: str,
) -> Iterable[Term]:
    path = os.path.join(directory, f'{identifier}.json')
    if identifier in visited_identifiers:
        return
    visited_identifiers.add(identifier)

    if os.path.exists(path):
        with open(path) as file:
            res_json = json.load(file)
    else:
        res_json = _get_entity(identifier)
        with open(path, 'w') as file:
            json.dump(res_json, file, indent=2)

    yield _extract(res_json)
    for identifier in _get_child_identifiers(res_json):
        yield from _visit(identifier, visited_identifiers, directory)


def _extract(res_json) -> Term:
    identifier = res_json['@id'][len(ICD11_TOP_LEVEL_URL):].lstrip('/')
    definition = res_json['definition']['@value'] if 'definition' in res_json else None
    name = res_json['title']['@value']
    synonyms = [
        Synonym(synonym['label']['@value'])
        for synonym in res_json.get('synonym', [])
    ]
    parents = [
        Reference(prefix=PREFIX, identifier=url[len('http://id.who.int/icd/entity/'):])
        for url in res_json['parent']
        if url[len('http://id.who.int/icd/entity/'):]
    ]
    return Term(
        reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        definition=definition,
        synonyms=synonyms,
        parents=parents,
    )


@click.command()
@verbose_option
def main():
    """Download the ICD11 data."""
    # get_obo().write_default(use_tqdm=True)
    for _ in tqdm(iterate_icd11(), desc=f'Downloading {PREFIX}', unit_scale=True):
        pass


if __name__ == '__main__':
    main()
