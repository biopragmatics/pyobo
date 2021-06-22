# -*- coding: utf-8 -*-

"""Converter for HGNC Gene Families."""

from collections import defaultdict
from typing import Iterable, List, Mapping

import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, SynonymTypeDef, Term, from_species
from ..utils.path import ensure_path

PREFIX = "hgnc.genefamily"
FAMILIES_URL = "ftp://ftp.ebi.ac.uk/pub/databases/genenames/new/csv/genefamily_db_tables/family.csv"
HIERARCHY_URL = (
    "ftp://ftp.ebi.ac.uk/pub/databases/genenames/new/csv/genefamily_db_tables/hierarchy.csv"
)

symbol_type = SynonymTypeDef(id="symbol", name="symbol")


def get_obo() -> Obo:
    """Get HGNC Gene Families as OBO."""
    return Obo(
        ontology=PREFIX,
        name="HGNC Gene Families",
        iter_terms=get_terms,
        synonym_typedefs=[symbol_type],
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_hierarchy() -> Mapping[str, List[str]]:
    """Get the HGNC Gene Families hierarchy as a dictionary."""
    path = ensure_path(PREFIX, url=HIERARCHY_URL)
    df = pd.read_csv(path, dtype={"parent_fam_id": str, "child_fam_id": str})
    d = defaultdict(list)
    for parent_id, child_id in df.values:
        d[child_id].append(parent_id)
    return dict(d)


COLUMNS = ["id", "abbreviation", "name", "pubmed_ids", "desc_comment", "desc_go"]


def get_terms() -> Iterable[Term]:
    """Get the HGNC Gene Family terms."""
    terms = list(_get_terms_helper())
    hierarchy = get_hierarchy()

    id_to_term = {term.reference.identifier: term for term in terms}
    for child_id, parent_ids in hierarchy.items():
        child = id_to_term[child_id]
        for parent_id in parent_ids:
            parent: Term = id_to_term[parent_id]
            child.parents.append(
                Reference(
                    prefix=PREFIX,
                    identifier=parent_id,
                    name=parent.name,
                )
            )
    return terms


def _get_terms_helper() -> Iterable[Term]:
    path = ensure_path(PREFIX, url=FAMILIES_URL)
    df = pd.read_csv(path, dtype={"id": str})

    it = tqdm(df[COLUMNS].values, desc=f"Mapping {PREFIX}")
    for hgncgenefamily_id, symbol, name, pubmed_ids, definition, desc_go in it:
        if pubmed_ids and pd.notna(pubmed_ids):
            provenance = [
                Reference(prefix="pubmed", identifier=s.strip()) for s in pubmed_ids.split(",")
            ]
        else:
            provenance = []

        if not definition or pd.isna(definition):
            definition = ""

        xrefs = []
        if desc_go and pd.notna(desc_go):
            go_id = desc_go[len("http://purl.uniprot.org/go/") :]
            xrefs.append(Reference(prefix="go", identifier=go_id))

        synonyms = []
        if symbol and pd.notna(symbol):
            synonyms.append(Synonym(name=symbol, type=symbol_type))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=hgncgenefamily_id, name=name),
            definition=definition,
            provenance=provenance,
            xrefs=xrefs,
            synonyms=synonyms,
        )
        term.set_species(identifier="9606", name="Homo sapiens")
        yield term


if __name__ == "__main__":
    get_obo().write_default()
