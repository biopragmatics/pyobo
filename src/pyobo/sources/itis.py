"""Converter for the Integrated Taxonomic Information System (ITIS)."""

import os
import shutil
import sqlite3
import zipfile
from collections.abc import Iterable
from contextlib import closing

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

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        # don't add force since the version getter already will
        return iter_terms(force=force, version=self._version_or_raise)


def get_obo() -> Obo:
    """Get ITIS as OBO."""
    return ITISGetter()


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get ITIS terms."""
    zip_path = ensure_path(PREFIX, url=URL, force=force, version=version)
    sqlite_dir = prefix_directory_join(PREFIX, version=version)
    sqlite_path = prefix_directory_join(PREFIX, name="itis.sqlite", version=version)
    if not os.path.exists(sqlite_path):
        with zipfile.ZipFile(zip_path) as zip_file:
            for file in zip_file.filelist:
                if file.filename.endswith(".sqlite") and not file.is_dir():
                    zip_file.extract(file, sqlite_dir)
                    shutil.move(os.path.join(sqlite_dir, file.filename), sqlite_path)
                    os.rmdir(os.path.join(sqlite_dir, os.path.dirname(file.filename)))

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
    ITISGetter.cli()
