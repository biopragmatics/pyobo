# -*- coding: utf-8 -*-

"""Converter for bigg."""

import bioversions
from typing import Iterable
from pyobo.path_utils import ensure_df, ensure_tar_df
from pyobo.struct import Obo, Reference, Synonym, SynonymTypeDef, Term, from_species, TypeDef

HEADER = ['bigg_id', 'universal_bigg_id', 'name', 'model_list', 'database_links',
          'old_bigg_ids']
PREFIX = 'bigg'

URL = 'http://bigg.ucsd.edu/static/namespace/bigg_models_metabolites.txt'

alias_type = SynonymTypeDef(id="alias", name="alias")
has_role = TypeDef(reference=Reference(prefix="bigg", identifier="has_role"))


def get_obo(force: bool = False) -> Obo:
    """Get bigg as OBO."""
    version = bioversions.get_version("bigg")
    #version = '1.2'
    return Obo(
        ontology=PREFIX,
        name="bigg models metabolites database",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=False),
        typedefs=[has_role],
        synonym_typedefs=[alias_type],
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
    )


def get_terms(force: bool = False) -> Iterable[Term]:
    bigg_df = ensure_df(
        prefix=PREFIX,
        url=URL,
        sep="\t",
        skiprows=18,
        header=None,
        names=HEADER,
        )

    for r, c in bigg_df.iterrows():
        bigg_id = c[0]
        name = c[2]
        synonyms = []
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=bigg_id, name=name),
            definition=[],
            synonyms=synonyms,
        )
        yield term


if __name__ == "__main__":
    get_obo(force=True).cli()
