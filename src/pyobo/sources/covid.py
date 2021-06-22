# -*- coding: utf-8 -*-

"""Convert Fraunhofer COVID terminology to OBO."""

from typing import Iterable

import pandas as pd

from ..struct import Obo, Reference, Term

prefix = "covid"

URL = "https://raw.githubusercontent.com/covid19kg/covid19kg/master/supplement/terminology.csv"


def get_obo() -> Obo:
    """Return the Fraunhofer COVID 19 terminology as OBO."""
    return Obo(
        ontology=prefix,
        name="Fraunhofer COVID terminology",
        iter_terms=iter_terms,
        auto_generated_by=f"bio2obo:{prefix}",
    )


def iter_terms() -> Iterable[Term]:
    """Iterate terms of COVID."""
    # ID,AUTHOR,TERM,TYPE,REFERENCE,DESCRIPTION,TAXONOMY
    df = pd.read_csv(URL)
    for identifier, name, definition in df[["ID", "TERM", "DESCRIPTION"]].values:
        yield Term(
            reference=Reference(prefix=prefix, identifier=identifier, name=name),
            definition=definition,
        )


if __name__ == "__main__":
    get_obo().write_default()
