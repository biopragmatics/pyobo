# -*- coding: utf-8 -*-

"""Get Wikidata xrefs."""

from typing import Iterable, Tuple

import pandas as pd
import requests

from ...registries.registries import CURATED_REGISTRY_DATABASE

URL = 'https://query.wikidata.org/sparql'


def iterate_wikidata_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over WikiData xref dataframes."""
    for prefix, entry in CURATED_REGISTRY_DATABASE.items():
        wikidata_property = entry.get('wikidata_property')
        if wikidata_property is None:
            continue
        yield get_wikidata_df(prefix, wikidata_property)


def get_wikidata_df(prefix: str, wikidata_property: str) -> pd.DataFrame:
    """Get Wikidata xrefs."""
    return pd.DataFrame(
        [
            ('wikidata', wikidata_id, prefix, external_id, 'wikidata')
            for wikidata_id, external_id in iter_wikidata_mappings(wikidata_property)
        ],
        columns=['source_ns', 'source_id', 'target_ns', 'target_id', 'source'],
    )


def iter_wikidata_mappings(wikidata_property: str) -> Iterable[Tuple[str, str]]:
    """Iterate over Wikidata xrefs."""
    query = f"SELECT ?wikidata_id ?id WHERE {{?wikidata_id wdt:{wikidata_property} ?id}}"
    res = requests.get(URL, params=dict(query=query, format='json'))
    for d in res.json()['results']['bindings']:
        wikidata_id = d['wikidata_id']['value'][len('http://wikidata.org/entity/'):]
        entity_id = d['id']['value']
        yield wikidata_id, entity_id
