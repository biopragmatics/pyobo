# -*- coding: utf-8 -*-

"""Converter for PathBank."""

import logging
from collections import defaultdict
from typing import Iterable, Mapping, Set

import pandas as pd
from tqdm import tqdm

from ..path_utils import ensure_df
from ..struct import Obo, Reference, Term, TypeDef
from ..struct.defs import is_a, pathway_has_part

logger = logging.getLogger(__name__)

PREFIX = 'pathbank'

PATHWAY_URL = 'https://pathbank.org/downloads/pathbank_all_pathways.csv.zip'
PATHWAY_COLUMNS = [
    'SMPDB ID',
    'PW ID',
    'Name',
    'Subject',
    'Description',
]

PROTEINS_URL = 'https://pathbank.org/downloads/pathbank_all_proteins.csv.zip'
PROTEINS_COLUMNS = [
    'PathBank ID', 'Pathway Name', 'Pathway Subject', 'Species', 'Uniprot ID',
    'Protein Name', 'HMDBP ID', 'DrugBank ID', 'GenBank ID', 'Gene Name', 'Locus',
]

METABOLITE_URL = 'https://pathbank.org/downloads/pathbank_all_metabolites.csv.zip'
METABOLITE_COLUMNS = [
    'PathBank ID', 'Pathway Name', 'Pathway Subject', 'Species', 'Metabolite ID', 'Metabolite Name',
    'HMDB ID', 'KEGG ID', 'ChEBI ID', 'DrugBank ID', 'CAS', 'Formula', 'IUPAC', 'SMILES', 'InChI', 'InChI Key',
]

pathway_type = TypeDef(
    reference=Reference(prefix=PREFIX, identifier='pathway_type', name='pathway is a'),
    parents=[is_a],
)


def get_obo() -> Obo:
    """Get PathBank as OBO."""
    return Obo(
        ontology=PREFIX,
        name='PathBank',
        typedefs=[pathway_type],
        iter_terms=iter_terms,
    )


def get_proteins_df() -> pd.DataFrame:
    """Get the proteins dataframe."""
    proteins_df = ensure_df(
        PREFIX, PROTEINS_URL, sep=',',
        usecols=['PathBank ID', 'Uniprot ID'],
    )
    proteins_df = proteins_df[proteins_df['Uniprot ID'].notna()]
    proteins_df = proteins_df[proteins_df['Uniprot ID'] != 'Unknown']
    proteins_df['Uniprot ID'] = proteins_df['Uniprot ID'].map(str.strip)
    return proteins_df


def get_protein_mapping() -> Mapping[str, Set[Reference]]:
    """Make the protein mapping."""
    proteins_df = get_proteins_df()
    smpdb_id_to_proteins = defaultdict(set)
    for pathway_id, protein_id in tqdm(proteins_df.values, desc='mapping proteins'):
        # TODO get protein names
        smpdb_id_to_proteins[pathway_id].add(Reference(prefix='uniprot', identifier=protein_id))
    return smpdb_id_to_proteins


def get_metabolite_df() -> pd.DataFrame:
    """Get the metabolites dataframe."""
    return ensure_df(
        PREFIX, METABOLITE_URL, sep=',',
        usecols=['PathBank ID', 'Metabolite ID', 'Metabolite Name'],
    )


def get_metabolite_mapping() -> Mapping[str, Set[Reference]]:
    """Make the metabolite mapping."""
    metabolites_df = get_metabolite_df()
    smpdb_id_to_metabolites = defaultdict(set)
    for pathway_id, metabolite_id, metabolite_name in tqdm(metabolites_df.values, desc='mapping metabolites'):
        smpdb_id_to_metabolites[pathway_id].add(Reference(
            prefix=PREFIX, identifier=metabolite_id, name=metabolite_name,
        ))
    return smpdb_id_to_metabolites


def iter_terms() -> Iterable[Term]:
    """Get PathBank's terms."""
    smpdb_id_to_proteins = get_protein_mapping()
    smpdb_id_to_metabolites = get_metabolite_mapping()

    pathways_df = ensure_df(PREFIX, PATHWAY_URL, sep=',')
    it = tqdm(pathways_df.values, total=len(pathways_df.index), desc=f'mapping {PREFIX}')
    for smpdb_id, pathbank_id, name, subject, _description in it:
        reference = Reference(prefix=PREFIX, identifier=pathbank_id, name=name)
        term = Term(
            reference=reference,
            # definition=description.replace('\n', ' '),
            xrefs=[Reference(prefix='smpdb', identifier=smpdb_id)],
        )
        term.append_relationship(pathway_type, Reference(
            prefix=PREFIX, identifier=subject.lower().replace(' ', '_'), name=subject,
        ))
        term.extend_relationship(pathway_has_part, smpdb_id_to_proteins[smpdb_id])
        term.extend_relationship(pathway_has_part, smpdb_id_to_metabolites[smpdb_id])
        yield term


if __name__ == '__main__':
    get_obo().write_default()
