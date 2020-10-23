# -*- coding: utf-8 -*-

"""Convert ICD11 to OBO.

Run with python -m pyobo.sources.icd11 -v
"""

import json
import logging
import os
from typing import Any, Iterable, Mapping

import click
from tqdm import tqdm

from ..cli_utils import verbose_option
from ..path_utils import get_prefix_directory
from ..sources.icd_utils import ICD11_TOP_LEVEL_URL, get_child_identifiers, get_icd, visiter
from ..struct import Obo, Reference, Synonym, Term

logger = logging.getLogger(__name__)

PREFIX = 'icd11'


def get_obo() -> Obo:
    """Get ICD11 as OBO."""
    return Obo(
        ontology=PREFIX,
        name='International Statistical Classification of Diseases and Related Health Problems 11th Revision',
        iter_terms=iterate_icd11,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def iterate_icd11() -> Iterable[Term]:
    """Iterate over the terms in ICD11.

    The API doesn't seem to have a rate limit, but returns pretty slow.
    This means that it only gets results at at about 5 calls/second.
    Get ready to be patient - the API token expires every hour so there's
    a caching mechanism with :mod:`cachier` that gets a new one every hour.
    """
    res = get_icd(ICD11_TOP_LEVEL_URL)
    res_json = res.json()

    version = res_json['releaseId']
    directory = get_prefix_directory(PREFIX, version=version)

    with open(os.path.join(directory, 'top.json'), 'w') as file:
        json.dump(res_json, file, indent=2)

    tqdm.write(f'There are {len(res_json["child"])} top level entities')

    visited_identifiers = set()
    for identifier in get_child_identifiers(ICD11_TOP_LEVEL_URL, res_json):
        yield from visiter(
            identifier,
            visited_identifiers,
            directory,
            endpoint=ICD11_TOP_LEVEL_URL,
            converter=_extract_icd11,
        )


def _extract_icd11(res_json: Mapping[str, Any]) -> Term:
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
def _main():
    get_obo().write_default(use_tqdm=True)


if __name__ == '__main__':
    _main()
