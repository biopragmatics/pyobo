# -*- coding: utf-8 -*-

"""Converter for ComplexPortal."""

import logging
from typing import Iterable, List, Tuple

import pandas as pd
from tqdm import tqdm

from pyobo import get_id_name_mapping
from pyobo.path_utils import ensure_df
from pyobo.struct import Obo, Reference, Synonym, Term, from_species, has_part

logger = logging.getLogger(__name__)

PREFIX = 'complexportal'
VERSION = '2020-03-11'
URL_BASE = f'ftp://ftp.ebi.ac.uk/pub/databases/intact/complex/{VERSION}/complextab'
SPECIES = [
    'arabidopsis_thaliana',
    'bos_taurus',
    'caenorhabditis_elegans',
    'canis_familiaris',
    'danio_rerio',
    'drosophila_melanogaster',
    'escherichia_coli',
    'gallus_gallus',
    'homo_sapiens',
    'lymnaea_stagnalis',
    'mus_musculus',
    'oryctolagus_cuniculus',
    'ovis_aries',
    'pseudomonas_aeruginosa',
    'rattus_norvegicus',
    'saccharomyces_cerevisiae',
    'schizosaccharomyces_pombe',
    'sus_scrofa',
    'torpedo_californica',
    'torpedo_marmorata',
    'xenopus_laevis',
]
URLS = [f'{URL_BASE}/{species}.tsv' for species in SPECIES]

COLUMNS = [
    'complexportal_id',
    'name',
    'aliases',
    'taxonomy_id',
    'members',
    'confidence',
    'experimental_evidence',
    'goa',
    'xrefs',
    'definition',
    'Complex properties',
    'Complex assembly',
    'Ligand',
    'Disease',
    'Agonist',
    'Antagonist',
    'Comment',
    'Source',
]
DTYPE = {
    'taxonomy_id': str,
}


def _parse_members(s) -> List[Tuple[Reference, str]]:
    if pd.isna(s):
        return []

    rv = []
    for member in s.split('|'):
        entity_id, count = member.split('(')
        count = count.rstrip(')')
        if ':' in entity_id:
            prefix, identifier = entity_id.split(':', 1)
        else:
            prefix, identifier = 'uniprot', entity_id
        rv.append((Reference(prefix=prefix, identifier=identifier), count))
    return rv


def _parse_xrefs(s) -> List[Tuple[Reference, str]]:
    if pd.isna(s):
        return []

    rv = []
    for xref in s.split('|'):
        entity_id, note = xref.split('(')
        note = note.rstrip(')')
        prefix, identifier = entity_id.split(':', 1)
        rv.append((Reference(prefix=prefix, identifier=identifier), note))
    return rv


def get_obo() -> Obo:
    """Get the ComplexPortal OBO."""
    return Obo(
        ontology=PREFIX,
        name='Complex Portal',
        data_version=VERSION,
        iter_terms=get_terms,
        typedefs=[from_species, has_part],
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def get_df() -> pd.DataFrame:
    """Get a combine ComplexPortal dataframe."""
    dfs = [
        ensure_df(PREFIX, url, version=VERSION, na_values={'-'}, names=COLUMNS, header=0, dtype=DTYPE)
        for url in URLS
    ]
    return pd.concat(dfs)


def get_terms() -> Iterable[Term]:
    """Get ComplexPortal terms."""
    df = get_df()

    df['aliases'] = df['aliases'].map(lambda s: s.split('|') if pd.notna(s) else [])
    df['members'] = df['members'].map(_parse_members)
    df['xrefs'] = df['xrefs'].map(_parse_xrefs)

    taxnomy_id_to_name = get_id_name_mapping('ncbitaxon')
    df['taxonomy_name'] = df['taxonomy_id'].map(taxnomy_id_to_name.get)

    slim_df = df[[
        'complexportal_id',
        'name',
        'definition',
        'aliases',
        'xrefs',
        'taxonomy_id',
        'taxonomy_name',
        'members',
    ]]
    it = tqdm(slim_df.values, total=len(slim_df.index), desc=f'mapping {PREFIX}')
    unhandled_xref_type = set()
    for complexportal_id, name, definition, aliases, xrefs, taxonomy_id, taxonomy_name, members in it:
        synonyms = [
            Synonym(name=alias)
            for alias in aliases
        ]
        _xrefs = []
        provenance = []
        for reference, note in xrefs:
            if note == 'identity':
                _xrefs.append(reference)
            elif note == 'see-also' and reference.prefix == 'pubmed':
                provenance.append(reference)
            elif (note, reference.prefix) not in unhandled_xref_type:
                it.write(f'unhandled xref type: {note} / {reference.prefix}')
                unhandled_xref_type.add((note, reference.prefix))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=complexportal_id, name=name),
            definition=definition.strip(),
            synonyms=synonyms,
            xrefs=_xrefs,
            provenance=provenance,
        )
        term.append_relationship(from_species, Reference(prefix='taxonomy', identifier=taxonomy_id, name=taxonomy_name))

        for reference, _count in members:
            term.append_relationship(has_part, reference)

        yield term


if __name__ == '__main__':
    get_obo().write_default()
