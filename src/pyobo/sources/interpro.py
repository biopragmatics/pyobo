# -*- coding: utf-8 -*-

"""Converter for InterPro."""

from collections import defaultdict
from typing import Iterable, Mapping, Set, Tuple

import bioversions
from tqdm import tqdm

from .utils import get_go_mapping
from ..struct import Obo, Reference, Term
from ..struct.typedef import has_member
from ..utils.io import multisetdict
from ..utils.path import ensure_df, ensure_path

PREFIX = "interpro"

#: Data source for protein-interpro mappings
INTERPRO_PROTEIN_COLUMNS = [
    "uniprot_id",
    "interpro_id",
    "interpro_name",
    "xref",  # either superfamily, gene family gene scan, PFAM, TIGERFAM
    "start",  # int
    "end",  # int
]


def get_obo() -> Obo:
    """Get InterPro as OBO."""
    version = bioversions.get_version(PREFIX)

    return Obo(
        ontology=PREFIX,
        name="InterPro",
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
    )


def iter_terms(*, version: str, proteins: bool = False) -> Iterable[Term]:
    """Get InterPro terms."""
    parents = get_interpro_tree(version=version)
    interpro_to_gos = get_interpro_go_df(version=version)
    interpro_to_proteins = get_interpro_to_proteins_df(version=version) if proteins else {}

    entries_df = ensure_df(
        PREFIX,
        url=f"ftp://ftp.ebi.ac.uk/pub/databases/interpro/{version}/entry.list",
        skiprows=1,
        names=("ENTRY_AC", "ENTRY_TYPE", "ENTRY_NAME"),
    )

    references = {
        identifier: Reference(prefix=PREFIX, identifier=identifier, name=name)
        for identifier, _, name in tqdm(entries_df.values)
    }

    for identifier, entry_type, _ in tqdm(entries_df.values):
        xrefs = []
        for go_id, go_name in interpro_to_gos.get(identifier, []):
            xrefs.append(Reference("go", go_id, go_name))

        term = Term(
            reference=references[identifier],
            xrefs=xrefs,
            parents=[references[parent_id] for parent_id in parents.get(identifier, [])],
        )
        term.append_property("type", entry_type)
        for uniprot_id in interpro_to_proteins.get(identifier, []):
            term.append_relationship(has_member, Reference("uniprot", uniprot_id))
        yield term


def get_interpro_go_df(version: str) -> Mapping[str, Set[Tuple[str, str]]]:
    """Get InterPro to Gene Ontology molecular function mapping."""
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/interpro/{version}/interpro2go"
    path = ensure_path(PREFIX, url=url, name="interpro2go.tsv", version=version)
    return get_go_mapping(path, prefix=PREFIX)


def get_interpro_tree(version: str):
    """Get InterPro Data source."""
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/interpro/{version}/ParentChildTreeFile.txt"
    path = ensure_path(PREFIX, url=url, version=version)
    with open(path) as f:
        return _parse_tree_helper(f)


def _parse_tree_helper(lines: Iterable[str]):
    rv = defaultdict(list)
    previous_depth, previous_id = 0, None
    stack = [previous_id]

    for line in tqdm(lines, desc="parsing InterPro tree"):
        depth = _count_front(line)
        parent_id, _ = line[depth:].split("::")

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
        if element != "-":
            return position


def get_interpro_to_proteins_df(version: str):
    """Get InterPro to Protein dataframe."""
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/interpro/{version}/protein2ipr.dat.gz"
    df = ensure_df(
        PREFIX,
        url=url,
        compression="gzip",
        usecols=[0, 1, 3],
        names=INTERPRO_PROTEIN_COLUMNS,
    )
    return multisetdict((interpro_id, uniprot_id) for uniprot_id, interpro_id in df.values)


if __name__ == "__main__":
    get_obo().write_default()
