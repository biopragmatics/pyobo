# -*- coding: utf-8 -*-

"""Get Wikidata xrefs.

Run with python -m pyobo.xrefdb.sources.wikidata
"""

import logging
from typing import Iterable, Tuple

import click
import pandas as pd
import requests

from ...cli_utils import verbose_option
from ...constants import XREF_COLUMNS
from ...registries import get_curated_registry_database

logger = logging.getLogger(__name__)

#: WikiData SPARQL endpoint. See https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service#Interfacing
URL = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'


def iterate_wikidata_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over WikiData xref dataframes."""
    for prefix, entry in get_curated_registry_database().items():
        wikidata_property = entry.get('wikidata_property')
        if wikidata_property is None:
            continue
        yield get_wikidata_df(prefix, wikidata_property)


def get_wikidata_df(prefix: str, wikidata_property: str) -> pd.DataFrame:
    """Get Wikidata xrefs."""
    df = pd.DataFrame(
        [
            ('wikidata', wikidata_id, prefix, external_id, 'wikidata')
            for wikidata_id, external_id in iter_wikidata_mappings(wikidata_property)
        ],
        columns=XREF_COLUMNS,
    )
    logger.info('got wikidata (%s; %s): %d rows', prefix, wikidata_property, len(df.index))
    return df


def iter_wikidata_mappings(wikidata_property: str) -> Iterable[Tuple[str, str]]:
    """Iterate over Wikidata xrefs."""
    query = f"SELECT ?wikidata_id ?id WHERE {{?wikidata_id wdt:{wikidata_property} ?id}}"
    logger.debug('running query: %s', query)
    res = requests.get(URL, params={'query': query, 'format': 'json'})
    res.raise_for_status()
    res_json = res.json()
    for d in res_json['results']['bindings']:
        wikidata_id = d['wikidata_id']['value'][len('http://wikidata.org/entity/'):]
        entity_id = d['id']['value']
        yield wikidata_id, entity_id


@click.command()
@verbose_option
def _main():
    """Summarize xrefs."""
    for _ in iterate_wikidata_dfs():
        pass


if __name__ == '__main__':
    _main()
