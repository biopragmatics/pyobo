# -*- coding: utf-8 -*-

"""Get Wikidata xrefs.

Run with python -m pyobo.xrefdb.sources.wikidata
"""

import logging
from functools import lru_cache
from typing import Iterable, Tuple

import click
import pandas as pd
import requests

from ...cli_utils import verbose_option
from ...constants import XREF_COLUMNS
from ...identifier_utils import normalize_curie
from ...registries import get_curated_registry_database, get_wikidata_property_types

logger = logging.getLogger(__name__)

#: WikiData SPARQL endpoint. See https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service#Interfacing
URL = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'


def get_wikidata_xrefs_df() -> pd.DataFrame:
    """Get all Wikidata xrefs."""
    return pd.concat(iterate_wikidata_dfs())


def iterate_wikidata_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over WikiData xref dataframes."""
    yield get_exact_matches_df('Q21014462')  # cell line
    wikidata_properties = _get_curated_wikidata_properties()
    wikidata_properties.update(get_wikidata_properties())
    for prefix, wikidata_property in wikidata_properties.items():
        yield get_wikidata_df(prefix, wikidata_property)


@lru_cache
def _get_curated_wikidata_properties():
    return {
        prefix: entry['wikidata_property']
        for prefix, entry in get_curated_registry_database().items()
        if 'wikidata_property' in entry
    }


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
        query = f"""
        SELECT ?item ?itemLabel
        WHERE {{ 
            ?item wdt:P31 wd:{wdp}. 
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}"""
        for d in _run_query(query):
            yield d['item']['value'][len('http://www.wikidata.org/entity/'):], d['itemLabel']['value']


def _run_query(query):
    logger.debug('running query: %s', query)
    res = requests.get(URL, params={'query': query, 'format': 'json'})
    res.raise_for_status()
    res_json = res.json()
    return res_json['results']['bindings']


def get_exact_matches_df(type_wikidata_id: str) -> pd.DataFrame:
    """Get exact matches dataframe."""
    df = pd.DataFrame(
        [
            ('wikidata', wikidata_id, prefix, identifier, 'wikidata')
            for wikidata_id, prefix, identifier in get_exact_matches(type_wikidata_id)
        ],
        columns=XREF_COLUMNS,
    )
    logger.info('got %d wikidata exact matches for type %s', len(df.index), type_wikidata_id)
    return df


def get_exact_matches(type_wikidata_id: str = 'Q21014462') -> Iterable[Tuple[str, str, str]]:
    """Get exact matches."""
    query = f"""
    SELECT ?wikidata_id ?id
    WHERE
    {{
        ?wikidata_id wdt:P31 wd:{type_wikidata_id} .
        ?wikidata_id wdt:P2888 ?value .
        FILTER( strStarts( str(?value), "http://purl.obolibrary.org/obo/" ) ) .
        BIND( SUBSTR(str(?value), 1 + STRLEN("http://purl.obolibrary.org/obo/")) as ?id ).
    }}
    """
    res = requests.get(URL, params={'query': query, 'format': 'json'})
    res.raise_for_status()
    res_json = res.json()
    for d in res_json['results']['bindings']:
        wikidata_id = d['wikidata_id']['value'][len('http://wikidata.org/entity/'):]
        prefix, identifier = normalize_curie(d['id']['value'].replace('_', ':', 1))
        if prefix and identifier:
            yield wikidata_id, prefix, identifier


@click.command()
@verbose_option
def _main():
    """Summarize xrefs."""
    cp = _get_curated_wikidata_properties()
    for prop, name in get_wikidata_properties():
        if prop not in cp.values():
            print(prop, name)


if __name__ == '__main__':
    _main()
