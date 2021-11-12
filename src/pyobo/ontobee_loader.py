"""Some ontologies can't be loaded via OWL in Python, so query OntoBee directly."""

import logging
from io import StringIO

import pandas as pd
import requests
from rich import print

logger = logging.getLogger(__name__)
ENDPOINT = "http://sparql.hegroup.org/sparql"
QUERY = """
SELECT DISTINCT
    ?uri ?label
WHERE {{
    ?uri rdfs:label ?label .
    FILTER STRSTARTS(str(?uri), "http://purl.obolibrary.org/obo/{prefix}")
}}
LIMIT 5
"""


def _run_query(query, base: str):
    logger.debug("running query: %s", query)
    res = requests.get(base, params={"query": query, "format": "csv"})
    return pd.read_csv(StringIO(res.text), sep=",")


def main():
    res = _run_query(QUERY.format(prefix="UBERON"), ENDPOINT)
    print(res)


if __name__ == "__main__":
    main()
