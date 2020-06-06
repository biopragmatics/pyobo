# -*- coding: utf-8 -*-

"""Converter for ChEMBL."""

import logging
import os
import sqlite3
import tarfile
from contextlib import closing

import click
from tabulate import tabulate

from pyobo.cli_utils import verbose_option
from pyobo.path_utils import ensure_path, get_prefix_directory

logger = logging.getLogger(__name__)

PREFIX = 'chembl.compound'
VERSION = '27'
URL = f'ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{VERSION}/chembl_{VERSION}_sqlite.tar.gz'

QUERY = '''
SELECT
    MOLECULE_DICTIONARY.chembl_id,
    MOLECULE_DICTIONARY.pref_name,
    COMPOUND_STRUCTURES.standard_inchi
FROM MOLECULE_DICTIONARY
JOIN COMPOUND_STRUCTURES ON MOLECULE_DICTIONARY.molregno == COMPOUND_STRUCTURES.molregno
WHERE molecule_dictionary.pref_name IS NOT NULL
limit 15
'''


def get_path():
    path = ensure_path(PREFIX, URL, version=VERSION)
    name = f'chembl_{VERSION}/chembl_{VERSION}_sqlite/chembl_{VERSION}.db'
    d = get_prefix_directory(PREFIX, version=VERSION)
    op = os.path.join(d, name)
    if not os.path.exists(op):
        with tarfile.open(path, mode='r', encoding='utf-8') as tar_file:
            tar_file.extractall(d)
    return op


def run():
    op = get_path()
    with closing(sqlite3.connect(op)) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute(QUERY)
            print(tabulate(cursor.fetchall()))


@click.command()
@verbose_option
def main():
    run()


if __name__ == '__main__':
    main()
