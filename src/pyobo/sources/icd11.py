# -*- coding: utf-8 -*-

"""Converter for ICD."""

import json
import logging
import os
from typing import Iterable

import click
import requests

from pyobo import Synonym
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


def iterate_icd11() -> Iterable[Term]:
    grant_type = 'client_credentials'
    body_params = {'grant_type': grant_type}
    res = requests.post(TOKEN_URL, data=body_params, auth=(CLIENT_ID, CLIENT_SECRET))
    res_json = res.json()
    access_type = res_json['token_type']
    access_token = res_json['access_token']

    headers = {
        'API-Version': 'v2',
        'Accept-Language': 'en',
        'Authorization': f'{access_type} {access_token}',
    }

    res = requests.get(ICD11_TOP_LEVEL_URL, headers=headers)
    res_json = res.json()

    version = res_json['releaseId']
    directory = get_prefix_directory(PREFIX, version=version)

    with open(os.path.join(directory, 'top.json'), 'w') as file:
        json.dump(res_json, file, indent=2)

    child_urls = res_json['child']
    logger.info('There are %d top level entities', len(child_urls))

    visited_urls = set()
    for child_url in child_urls:
        yield from _visit(child_url, visited_urls, headers, directory)


def _visit(url: str, visited_urls, headers, directory) -> Iterable[Term]:
    if url in visited_urls:
        return
    visited_urls.add(url)
    _res = requests.get(url, headers=headers)
    _res_json = _res.json()

    identifier = _res_json['@id'][len('http://id.who.int/icd/entity/'):]
    with open(os.path.join(directory, f'{identifier}.json'), 'w') as file:
        json.dump(_res_json, file, indent=2)

    yield _extract(_res_json)
    for _child_url in _res_json.get('child', []):
        yield from _visit(_child_url, visited_urls, headers, directory)


def _extract(res_json) -> Term:
    identifier = res_json['@id'][len('http://id.who.int/icd/entity/'):]
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
def main():
    get_obo().write_default(use_tqdm=True)


if __name__ == '__main__':
    main()
