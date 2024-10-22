"""Get Wikidata xrefs.

Run with ``python -m pyobo.xrefdb.sources.wikidata``.
"""

import json
import logging
from collections.abc import Iterable

import bioregistry
import click
import pandas as pd
import requests
from more_click import verbose_option
from tqdm.auto import tqdm

from ...constants import RAW_MODULE, XREF_COLUMNS
from ...version import get_version

logger = logging.getLogger(__name__)

#: WikiData SPARQL endpoint. See https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service#Interfacing
URL = "https://query.wikidata.org/bigdata/namespace/wdq/sparql"

WIKIDATA_MAPPING_DIRECTORY = RAW_MODULE.module("wikidata", "mappings")


def get_wikidata_xrefs_df(*, use_tqdm: bool = True) -> pd.DataFrame:
    """Get all Wikidata xrefs."""
    return pd.concat(iterate_wikidata_dfs(use_tqdm=use_tqdm))


def iterate_wikidata_dfs(*, use_tqdm: bool = True) -> Iterable[pd.DataFrame]:
    """Iterate over WikiData xref dataframes."""
    wikidata_properties = {
        prefix: entry.wikidata["prefix"]
        for prefix, entry in bioregistry.read_registry().items()
        if entry.wikidata and "prefix" in entry.wikidata
    }

    it = tqdm(sorted(wikidata_properties.items()), disable=not use_tqdm, desc="Wikidata properties")
    for prefix, wikidata_property in it:
        if prefix in {"pubmed", "pmc", "orcid", "inchi", "smiles"}:
            continue  # too many
        it.set_postfix({"prefix": prefix})
        try:
            yield get_wikidata_df(prefix, wikidata_property)
        except json.decoder.JSONDecodeError as e:
            logger.warning(
                "[%s] Problem decoding results from %s: %s", prefix, wikidata_property, e
            )


def get_wikidata_df(prefix: str, wikidata_property: str) -> pd.DataFrame:
    """Get Wikidata xrefs."""
    df = pd.DataFrame(
        [
            ("wikidata", wikidata_id, prefix, external_id, "wikidata")
            for wikidata_id, external_id in iter_wikidata_mappings(wikidata_property)
        ],
        columns=XREF_COLUMNS,
    )
    logger.debug("got wikidata (%s; %s): %d rows", prefix, wikidata_property, len(df.index))
    return df


def iter_wikidata_mappings(
    wikidata_property: str, *, cache: bool = True
) -> Iterable[tuple[str, str]]:
    """Iterate over Wikidata xrefs."""
    path = WIKIDATA_MAPPING_DIRECTORY.join(name=f"{wikidata_property}.json")
    if path.exists() and cache:
        with path.open() as file:
            rows = json.load(file)
    else:
        query = f"SELECT ?wikidata_id ?id WHERE {{?wikidata_id wdt:{wikidata_property} ?id}}"
        rows = _run_query(query)
        with path.open("w") as file:
            json.dump(rows, file, indent=2)

    for row in rows:
        wikidata_id = _removeprefix(row["wikidata_id"]["value"], "http://www.wikidata.org/entity/")
        wikidata_id = _removeprefix(wikidata_id, "http://wikidata.org/entity/")
        entity_id = row["id"]["value"]
        yield wikidata_id, entity_id


def _removeprefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


HEADERS = {
    "User-Agent": f"pyobo/{get_version()}",
}


def _run_query(query, base: str = URL):
    logger.debug("running query: %s", query)
    res = requests.get(base, params={"query": query, "format": "json"}, headers=HEADERS)
    res.raise_for_status()
    res_json = res.json()
    return res_json["results"]["bindings"]


@click.command()
@verbose_option
def _main():
    """Summarize xrefs."""
    for _ in iterate_wikidata_dfs():
        pass


if __name__ == "__main__":
    _main()
