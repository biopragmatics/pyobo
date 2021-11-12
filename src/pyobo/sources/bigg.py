# -*- coding: utf-8 -*-

"""Converter for bigg."""

from typing import Iterable, Optional

import bioversions

from pyobo.struct import Obo, Reference, SynonymTypeDef, Term, TypeDef

from ..utils.path import ensure_df

HEADER = ["bigg_id", "universal_bigg_id", "name", "model_list", "database_links", "old_bigg_ids"]
PREFIX = "bigg.metabolite"

URL = "http://bigg.ucsd.edu/static/namespace/bigg_models_metabolites.txt"

alias_type = SynonymTypeDef(id="alias", name="alias")
has_role = TypeDef(reference=Reference(prefix="bigg", identifier="has_role"))


def get_obo(force: bool = False) -> Obo:
    """Get bigg as OBO."""
    version = bioversions.get_version("bigg")
    # version = '1.2'
    return Obo(
        ontology=PREFIX,
        name="bigg models metabolites database",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force, version=version),
        typedefs=[has_role],
        synonym_typedefs=[alias_type],
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
    )


def get_terms(force: bool = False, version: Optional[str] = None) -> Iterable[Term]:
    bigg_df = ensure_df(
        prefix=PREFIX,
        url=URL,
        sep="\t",
        skiprows=18,
        header=None,
        names=HEADER,
        usecols=["bigg_id", "name"],
        force=force,
        version=version,
    )

    for v in bigg_df.values:
        bigg_id = v[0]
        name = v[1]
        synonyms = []
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=bigg_id, name=name),
            synonyms=synonyms,
        )
        yield term


if __name__ == "__main__":
    get_obo(force=True).cli()
