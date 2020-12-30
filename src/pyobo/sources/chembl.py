# -*- coding: utf-8 -*-

"""Converter for ChEMBL.

Run with ``python -m pyobo.sources.chembl -vv``.
"""

import logging
import os
import sqlite3
import tarfile
from contextlib import closing
from typing import Iterable

import bioversions
import click

from pyobo.cli_utils import verbose_option
from pyobo.path_utils import ensure_path, get_prefix_directory
from pyobo.struct import Obo, Reference, Term

logger = logging.getLogger(__name__)

PREFIX = 'chembl.compound'

QUERY = '''
SELECT
    MOLECULE_DICTIONARY.chembl_id,
    MOLECULE_DICTIONARY.pref_name
FROM MOLECULE_DICTIONARY
JOIN COMPOUND_STRUCTURES ON MOLECULE_DICTIONARY.molregno == COMPOUND_STRUCTURES.molregno
WHERE molecule_dictionary.pref_name IS NOT NULL
'''


# TODO molecule_synonyms table
# TODO molecule_hierarchy table

def get_obo() -> Obo:
    """Return ChEMBL as OBO."""
    version = bioversions.get_version('chembl')
    return Obo(
        ontology='chembl.compound',
        name='ChEMBL',
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def get_path(version: str):
    """Get the path to the extracted ChEMBL SQLite database."""
    url = f'ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{version}/chembl_{version}_sqlite.tar.gz'
    path = ensure_path(PREFIX, url=url, version=version)
    name = f'chembl_{version}/chembl_{version}_sqlite/chembl_{version}.db'
    d = get_prefix_directory(PREFIX, version=version)
    op = os.path.join(d, name)
    if not os.path.exists(op):
        with tarfile.open(path, mode='r', encoding='utf-8') as tar_file:
            tar_file.extractall(d)
    return op


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over ChEMBL compound's names."""
    op = get_path(version=version)
    logger.info('opening connection to %s', op)
    with closing(sqlite3.connect(op)) as conn:
        logger.info('using connection %s', conn)
        with closing(conn.cursor()) as cursor:
            logger.info('using cursor %s', cursor)
            cursor.execute(QUERY)
            for chembl_id, name in cursor.fetchall():
                # TODO add xrefs to smiles, inchi, inchikey here
                xrefs = []
                yield Term(
                    reference=Reference(prefix=PREFIX, identifier=chembl_id, name=name),
                    xrefs=xrefs,
                )


@click.command()
@verbose_option
def main():
    """Write the default OBO."""
    get_obo().write_default()


if __name__ == '__main__':
    main()
