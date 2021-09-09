# -*- coding: utf-8 -*-

"""Converter for ChEMBL.

Run with ``python -m pyobo.sources.chembl -vv``.
"""

import logging
from contextlib import closing
from typing import Iterable

import bioversions
import chembl_downloader
import click
from more_click import verbose_option

from pyobo.struct import Obo, Reference, Term

logger = logging.getLogger(__name__)

PREFIX = "chembl.compound"

QUERY = """\
SELECT
    MOLECULE_DICTIONARY.chembl_id,
    MOLECULE_DICTIONARY.pref_name,
    COMPOUND_STRUCTURES.canonical_smiles,
    COMPOUND_STRUCTURES.standard_inchi,
    COMPOUND_STRUCTURES.standard_inchi_key
FROM MOLECULE_DICTIONARY
    JOIN COMPOUND_STRUCTURES ON MOLECULE_DICTIONARY.molregno == COMPOUND_STRUCTURES.molregno
WHERE
    molecule_dictionary.pref_name IS NOT NULL
"""


# TODO molecule_synonyms table
# TODO molecule_hierarchy table


def get_obo() -> Obo:
    """Return ChEMBL as OBO."""
    version = bioversions.get_version("chembl")
    return Obo(
        ontology="chembl.compound",
        name="ChEMBL",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over ChEMBL compounds."""
    with chembl_downloader.connect(version=version) as conn:
        logger.info("using connection %s", conn)
        with closing(conn.cursor()) as cursor:
            logger.info("using cursor %s", cursor)
            cursor.execute(QUERY)
            for chembl_id, name, smiles, inchi, inchi_key in cursor.fetchall():
                # TODO add xrefs?
                term = Term.from_triple(prefix=PREFIX, identifier=chembl_id, name=name)
                if smiles:
                    term.append_property("smiles", smiles)
                if inchi:
                    term.append_property("inchi", inchi)
                if inchi_key:
                    term.append_xref(Reference("inchikey", inchi_key))
                yield term


@click.command()
@verbose_option
def main():
    """Write the default OBO."""
    get_obo().write_default(force=True, use_tqdm=True)


if __name__ == "__main__":
    main()
