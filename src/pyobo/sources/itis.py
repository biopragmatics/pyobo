# -*- coding: utf-8 -*-

"""Converter for the Integrated Taxonomic Information System (ITIS)."""

import os
import sqlite3
import zipfile
from contextlib import closing
from typing import Iterable

from pyobo.io_utils import multidict
from pyobo.path_utils import ensure_path, get_prefix_directory, prefix_directory_join
from pyobo.struct import Obo, Reference, Term

PREFIX = 'itis'
URL = 'https://www.itis.gov/downloads/itisSqlite.zip'
VERSION = 'itisSqlite043020'

LONGNAMES_QUERY = """
SELECT tsn, completename
FROM longnames
"""

HIERARCHY_QUERY = """
SELECT TSN, Parent_TSN
FROM hierarchy
"""


def get_obo() -> Obo:
    """Get ITIS as OBO."""
    return Obo(
        ontology=PREFIX,
        name='Integrated Taxonomic Information System',
        iter_terms=iter_terms,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def iter_terms() -> Iterable[Term]:
    """Get ITIS terms."""
    zip_path = ensure_path(PREFIX, URL)
    sqlite_path = prefix_directory_join(PREFIX, 'itisSqlite043020', 'ITIS.sqlite')
    if not os.path.exists(sqlite_path):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(get_prefix_directory(PREFIX))

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f'file missing: {sqlite_path}')

    conn = sqlite3.connect(sqlite_path)

    with closing(conn.cursor()) as cursor:
        cursor.execute(LONGNAMES_QUERY)
        id_to_reference = {
            str(identifier): Reference(prefix=PREFIX, identifier=str(identifier), name=name)
            for identifier, name in cursor.fetchall()
        }

    with closing(conn.cursor()) as cursor:
        cursor.execute(HIERARCHY_QUERY)
        id_to_parents = multidict(
            (str(child), str(parent))
            for child, parent in cursor.fetchall()
        )

    for identifier, reference in id_to_reference.items():
        parents = []
        for parent_identifier in id_to_parents.get(identifier, []):
            if parent_identifier == '0':  # this means its a plant
                continue
            parents.append(id_to_reference[parent_identifier])
        term = Term(
            reference=reference,
            parents=parents,
        )
        yield term


if __name__ == '__main__':
    get_obo().write_default()
