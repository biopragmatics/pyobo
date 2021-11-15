# -*- coding: utf-8 -*-

"""Converter for the Integrated Taxonomic Information System (ITIS)."""

import os
import shutil
import sqlite3
import zipfile
from contextlib import closing
from typing import Iterable

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.io import multidict
from pyobo.utils.path import ensure_path, prefix_directory_join

__all__ = [
    "ITISGetter",
]

PREFIX = "itis"
URL = "https://www.itis.gov/downloads/itisSqlite.zip"

LONGNAMES_QUERY = """
SELECT tsn, completename
FROM longnames
"""

HIERARCHY_QUERY = """
SELECT TSN, Parent_TSN
FROM hierarchy
"""


# TODO confusing logic since you need to download the data first to get the version


class ITISGetter(Obo):
    """An ontology representation of the ITIS taxonomy."""

    ontology = PREFIX

    def _get_version(self) -> str:
        return _get_version(force=self.force)

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        # don't add force since the version getter already will
        return iter_terms()


def get_obo() -> Obo:
    """Get ITIS as OBO."""
    return ITISGetter()


def _get_version(force: bool = False) -> str:
    """Get the version of the current data."""
    zip_path = ensure_path(PREFIX, url=URL, force=force)
    with zipfile.ZipFile(zip_path) as zip_file:
        for x in zip_file.filelist:
            if x.filename.endswith(".sqlite"):
                return x.filename[len("itisSqlite") : -len("/ITIS.sqlite")]
    raise ValueError("could not find a file with the version in it")


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Get ITIS terms."""
    zip_path = ensure_path(PREFIX, url=URL, force=force)
    version = _get_version()
    sqlite_dir = prefix_directory_join(PREFIX, version=version)
    sqlite_path = prefix_directory_join(PREFIX, name="ITIS.sqlite", version=version)
    if not os.path.exists(sqlite_path):
        with zipfile.ZipFile(zip_path) as zip_file:
            for x in zip_file.filelist:
                if x.filename.endswith(".sqlite"):
                    zip_file.extract(x, sqlite_dir)
                    shutil.move(
                        os.path.join(sqlite_dir, f"itisSqlite{version}", "ITIS.sqlite"), sqlite_path
                    )
                    os.rmdir(os.path.join(sqlite_dir, f"itisSqlite{version}"))

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"file missing: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path.as_posix())

    with closing(conn.cursor()) as cursor:
        cursor.execute(LONGNAMES_QUERY)
        id_to_reference = {
            str(identifier): Reference(prefix=PREFIX, identifier=str(identifier), name=name)
            for identifier, name in cursor.fetchall()
        }

    with closing(conn.cursor()) as cursor:
        cursor.execute(HIERARCHY_QUERY)
        id_to_parents = multidict((str(child), str(parent)) for child, parent in cursor.fetchall())

    for identifier, reference in id_to_reference.items():
        parents = []
        for parent_identifier in id_to_parents.get(identifier, []):
            if parent_identifier == "0":  # this means it's a plant
                continue
            parents.append(id_to_reference[parent_identifier])
        term = Term(
            reference=reference,
            parents=parents,
        )
        yield term


if __name__ == "__main__":
    get_obo().write_default()
