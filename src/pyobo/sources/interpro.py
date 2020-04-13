# -*- coding: utf-8 -*-

"""Converter for InterPro."""

from collections import defaultdict
from typing import Iterable, Mapping, Set, Tuple

from tqdm import tqdm

from .utils import get_go_mapping
from ..io_utils import multisetdict
from ..path_utils import ensure_df, ensure_path
from ..struct import Obo, Reference, Term
from ..struct.typedef import has_member

PREFIX = 'interpro'

VERSION = '78.0'
BASE_URL = f'ftp://ftp.ebi.ac.uk/pub/databases/interpro/{VERSION}'
INTERPRO_ENTRIES_URL = f'{BASE_URL}/entry.list'

#: Data source for InterPro tree
INTERPRO_TREE_URL = f'{BASE_URL}/ParentChildTreeFile.txt'

#: Data source for protein-interpro mappings
INTERPRO_PROTEIN_URL = 'ftp://ftp.ebi.ac.uk/pub/databases/interpro/protein2ipr.dat.gz'
INTERPRO_PROTEIN_COLUMNS = [
    'uniprot_id',
    'interpro_id',
    'interpro_name',
    'xref',  # either superfamily, gene family gene scan, PFAM, TIGERFAM
    'start',  # int
    'end',  # int
]

#: Data source for interpro-GO mappings
INTERPRO_GO_MAPPING_URL = 'ftp://ftp.ebi.ac.uk/pub/databases/interpro/interpro2go'


def get_obo() -> Obo:
    """Get InterPro as OBO."""
    return Obo(
        ontology=PREFIX,
        name='InterPro',
        auto_generated_by=f'bio2obo:{PREFIX}',
        iter_terms=iter_terms,
    )


def iter_terms(proteins: bool = False) -> Iterable[Term]:
    """Get InterPro terms."""
    parents = get_interpro_tree()

    interpro_to_gos = get_interpro_go_df()

    interpro_to_proteins = get_interpro_to_proteins_df() if proteins else {}

    entries_df = ensure_df(
        PREFIX,
        INTERPRO_ENTRIES_URL,
        skiprows=1,
        names=('ENTRY_AC', 'ENTRY_TYPE', 'ENTRY_NAME'),
    )

    references = {
        identifier: Reference(prefix=PREFIX, identifier=identifier, name=name)
        for identifier, _, name in tqdm(entries_df.values)
    }

    for identifier, entry_type, _ in tqdm(entries_df.values):
        xrefs = []
        for go_id, go_name in interpro_to_gos.get(identifier, []):
            xrefs.append(Reference('go', go_id, go_name))

        term = Term(
            reference=references[identifier],
            xrefs=xrefs,
            parents=[
                references[parent_id]
                for parent_id in parents.get(identifier, [])
            ],
        )
        term.append_property('type', entry_type)
        for uniprot_id in interpro_to_proteins.get(identifier, []):
            term.append_relationship(has_member, Reference('uniprot', uniprot_id))
        yield term


def get_interpro_go_df() -> Mapping[str, Set[Tuple[str, str]]]:
    """Get InterPro to Gene Ontology molecular function mapping."""
    path = ensure_path(PREFIX, INTERPRO_GO_MAPPING_URL)
    return get_go_mapping(path, prefix=PREFIX)


def get_interpro_tree():
    """Get InterPro Data source."""
    path = ensure_path(PREFIX, INTERPRO_TREE_URL)
    with open(path) as f:
        return _parse_tree_helper(f)


def _parse_tree_helper(lines: Iterable[str]):
    rv = defaultdict(list)
    previous_depth, previous_id = 0, None
    stack = [previous_id]

    for line in tqdm(lines, desc='parsing InterPro tree'):
        depth = _count_front(line)
        parent_id, _, _ = line[depth:].split('::')

        if depth == 0:
            stack.clear()
            stack.append(parent_id)
        else:
            if depth > previous_depth:
                stack.append(previous_id)

            elif depth < previous_depth:
                del stack[-1]

            child_id = stack[-1]
            rv[child_id].append(parent_id)

        previous_depth, previous_id = depth, parent_id

    return dict(rv)


def _count_front(s: str) -> int:
    """Count the number of leading dashes on a string."""
    for position, element in enumerate(s):
        if element != '-':
            return position


def get_interpro_to_proteins_df():
    """Get InterPro to Protein dataframe."""
    df = ensure_df(
        PREFIX, INTERPRO_PROTEIN_URL,
        compression='gzip',
        usecols=[0, 1, 3],
        names=INTERPRO_PROTEIN_COLUMNS,
    )
    return multisetdict(
        (interpro_id, uniprot_id)
        for uniprot_id, interpro_id in df.values
    )


if __name__ == '__main__':
    get_obo().write_default()
