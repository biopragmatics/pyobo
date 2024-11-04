"""Converter for HGNC Gene Families."""

from collections import defaultdict
from collections.abc import Iterable, Mapping

import pandas as pd

from ..struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    enables,
    from_species,
)
from ..utils.path import ensure_path

__all__ = [
    "HGNCGroupGetter",
]

PREFIX = "hgnc.genegroup"
FAMILIES_URL = "https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/family.csv"
# TODO use family_alias.csv
HIERARCHY_URL = "https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/hierarchy.csv"

symbol_type = SynonymTypeDef(
    reference=Reference(prefix="OMO", identifier="0004000", name="has symbol")
)


class HGNCGroupGetter(Obo):
    """An ontology representation of HGNC's gene group nomenclature."""

    ontology = PREFIX
    bioversions_key = "hgnc"
    synonym_typedefs = [symbol_type]
    typedefs = [from_species, enables]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


def get_obo(force: bool = False) -> Obo:
    """Get HGNC Gene Groups as OBO."""
    return HGNCGroupGetter(force=force)


def get_hierarchy(force: bool = False) -> Mapping[str, list[str]]:
    """Get the HGNC Gene Families hierarchy as a dictionary."""
    path = ensure_path(PREFIX, url=HIERARCHY_URL, force=force)
    df = pd.read_csv(path, dtype={"parent_fam_id": str, "child_fam_id": str})
    d = defaultdict(list)
    for parent_id, child_id in df.values:
        d[child_id].append(parent_id)
    return dict(d)


COLUMNS = ["id", "abbreviation", "name", "pubmed_ids", "desc_comment", "desc_go"]


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get the HGNC Gene Group terms."""
    terms = list(_get_terms_helper(force=force))
    hierarchy = get_hierarchy(force=force)

    id_to_term = {term.reference.identifier: term for term in terms}
    for child_id, parent_ids in hierarchy.items():
        child: Term = id_to_term[child_id]
        for parent_id in parent_ids:
            parent: Term = id_to_term[parent_id]
            child.append_parent(
                Reference(
                    prefix=PREFIX,
                    identifier=parent_id,
                    name=parent.name,
                )
            )
    gene_group = Reference(prefix="SO", identifier="0005855", name="gene group")
    yield Term(reference=gene_group)
    for term in terms:
        if not term.parents:
            term.append_parent(gene_group)
    yield from terms


def _get_terms_helper(force: bool = False) -> Iterable[Term]:
    path = ensure_path(PREFIX, url=FAMILIES_URL, force=force)
    df = pd.read_csv(path, dtype={"id": str})

    for gene_group_id, symbol, name, pubmed_ids, definition, desc_go in df[COLUMNS].values:
        if not definition or pd.isna(definition):
            definition = None
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=gene_group_id, name=name),
            definition=definition,
        )
        if pubmed_ids and pd.notna(pubmed_ids):
            for s in pubmed_ids.replace(" ", ",").split(","):
                term.append_provenance(Reference(prefix="pubmed", identifier=s.strip()))
        if desc_go and pd.notna(desc_go):
            go_id = desc_go[len("http://purl.uniprot.org/go/") :]
            term.append_relationship(enables, Reference(prefix="GO", identifier=go_id))
        if symbol and pd.notna(symbol):
            term.append_synonym(Synonym(name=symbol, type=symbol_type))
        term.set_species(identifier="9606", name="Homo sapiens")
        yield term


if __name__ == "__main__":
    HGNCGroupGetter.cli()
