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
from ...registries import get_curated_registry_database, get_wikidata_property_types

logger = logging.getLogger(__name__)

#: WikiData SPARQL endpoint. See https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service#Interfacing
URL = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'


def get_wikidata_xrefs_df() -> pd.DataFrame:
    """Get all Wikidata xrefs."""
    return pd.concat(iterate_wikidata_dfs())


def iterate_wikidata_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over WikiData xref dataframes."""
    wikidata_properties = {
        prefix: entry['wikidata_property']
        for prefix, entry in get_curated_registry_database().items()
        if 'wikidata_property' in entry
    }
    # wikidata_properties.update(get_wikidata_properties())
    for prefix, wikidata_property in wikidata_properties.items():
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
    for d in _run_query(query):
        wikidata_id = d['wikidata_id']['value'][len('http://wikidata.org/entity/'):]
        entity_id = d['id']['value']
        yield wikidata_id, entity_id


def get_wikidata_properties() -> Iterable[str]:
    """Get child wikidata properties."""
    # TODO how to automatically assign prefixes?
    for wdp in get_wikidata_property_types():
        query = f"SELECT ?item WHERE {{ ?item wdt:P31 wd:{wdp} }}"
        for d in _run_query(query):
            yield d['item']['value'][len('wd:'):]


def _run_query(query):
    logger.debug('running query: %s', query)
    res = requests.get(URL, params={'query': query, 'format': 'json'})
    res.raise_for_status()
    res_json = res.json()
    return res_json['results']['bindings']


@click.command()
@verbose_option
def _main():
    """Summarize xrefs."""
    for _ in iterate_wikidata_dfs():
        pass


if __name__ == '__main__':
    _main()
