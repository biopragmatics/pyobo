# -*- coding: utf-8 -*-

"""Converter for Reactome."""

import logging
from typing import Iterable

import pandas as pd
from tqdm import tqdm

from ..constants import SPECIES_REMAPPING
from ..io_utils import multidict
from ..mappings import get_name_id_mapping
from ..path_utils import ensure_df
from ..struct import Obo, Reference, Term, from_species

logger = logging.getLogger(__name__)

PREFIX = 'reactome'

PATHWAY_NAMES_URL = 'https://reactome.org/download/current/ReactomePathways.txt'
PATHWAYS_HIERARCHY_URL = 'https://reactome.org/download/current/ReactomePathwaysRelation.txt'
PROVENANCE_URL = 'https://reactome.org/download/current/ReactionPMIDS.txt'


# TODO add protein mappings
# TODO add chemical mappings
# TODO alt ids https://reactome.org/download/current/reactome_stable_ids.txt

def get_obo() -> Obo:
    """Get Reactome OBO."""
    return Obo(
        ontology=PREFIX,
        name='Reactome',
        iter_terms=iter_terms,
        typedefs=[from_species],
    )


def iter_terms() -> Iterable[Term]:
    """Iterate Reactome terms."""
    ncbitaxon_name_to_id = get_name_id_mapping('ncbitaxon')

    provenance_df = ensure_df(PREFIX, PROVENANCE_URL, header=None)
    provenance_d = multidict(provenance_df.values)

    df = ensure_df(PREFIX, PATHWAY_NAMES_URL, header=None, names=['reactome_id', 'name', 'species'])
    df['species'] = df['species'].map(lambda x: SPECIES_REMAPPING.get(x) or x)
    df['taxonomy_id'] = df['species'].map(ncbitaxon_name_to_id.get)

    terms = {}
    it = tqdm(df.values, total=len(df.index), desc=f'mapping {PREFIX}')
    for reactome_id, name, species_name, taxonomy_id in it:
        terms[reactome_id] = term = Term(
            reference=Reference(prefix=PREFIX, identifier=reactome_id, name=name),
            provenance=[
                Reference(prefix='pubmed', identifier=pmid)
                for pmid in provenance_d.get(reactome_id, [])
            ],
        )
        if not taxonomy_id or pd.isna(taxonomy_id):
            raise ValueError(f'unmapped species: {species_name}')

        term.append_relationship(from_species, Reference(prefix='taxonomy', identifier=taxonomy_id, name=species_name))

    hierarchy_df = ensure_df(PREFIX, PATHWAYS_HIERARCHY_URL, header=None)
    for parent_id, child_id in hierarchy_df.values:
        terms[child_id].parents.append(terms[parent_id].reference)

    yield from terms.values()


if __name__ == '__main__':
    get_obo().write_default()
