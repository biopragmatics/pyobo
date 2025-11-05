"""Converter for HGNC Gene Families."""

from collections import defaultdict
from collections.abc import Iterable, Mapping

import pandas as pd

from ...struct import Obo, Reference, Term, is_mentioned_by
from ...struct.struct import abbreviation as symbol_type
from ...struct.typedef import enables, exact_match, from_species
from ...utils.path import ensure_df

__all__ = [
    "HGNCGroupGetter",
]

PREFIX = "hgnc.genegroup"
FAMILIES_URL = "https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/family.csv"
FAMILIES_ALIAS_URL = "https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/family_alias.csv"
HIERARCHY_URL = "https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/hierarchy.csv"


class HGNCGroupGetter(Obo):
    """An ontology representation of HGNC's gene group nomenclature."""

    ontology = PREFIX
    bioversions_key = "hgnc"
    synonym_typedefs = [symbol_type]
    typedefs = [from_species, enables, exact_match, is_mentioned_by]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


def get_hierarchy(force: bool = False) -> Mapping[str, list[str]]:
    """Get the HGNC Gene Families hierarchy as a dictionary."""
    df = ensure_df(PREFIX, url=HIERARCHY_URL, force=force, sep=",")
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
    alias_df = ensure_df(PREFIX, url=FAMILIES_ALIAS_URL, force=force, sep=",")
    aliases = defaultdict(set)
    for _id, family_id, alias in alias_df.values:
        aliases[family_id].add(alias)

    df = ensure_df(PREFIX, url=FAMILIES_URL, force=force, sep=",")
    for gene_group_id, symbol, name, pubmed_ids, definition, desc_go in df[COLUMNS].values:
        if not definition or pd.isna(definition):
            definition = None
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=gene_group_id, name=name),
            definition=definition,
        )
        if pubmed_ids and pd.notna(pubmed_ids):
            for s in pubmed_ids.replace(" ", ",").split(","):
                s = s.strip()
                if s:
                    term.append_mentioned_by(Reference(prefix="pubmed", identifier=s))
        if desc_go and pd.notna(desc_go):
            go_id = desc_go[len("http://purl.uniprot.org/go/") :]
            term.append_relationship(enables, Reference(prefix="GO", identifier=go_id))
        if symbol and pd.notna(symbol):
            term.append_synonym(symbol, type=symbol_type)
        for alias in aliases[gene_group_id]:
            term.append_synonym(alias)
        term.set_species(identifier="9606", name="Homo sapiens")
        yield term


if __name__ == "__main__":
    HGNCGroupGetter.cli()
