"""Converter for ChEMBL.

Run with ``python -m pyobo.sources.chembl -vv``.
"""

import logging
from collections.abc import Iterable
from contextlib import closing

import chembl_downloader

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import exact_match, has_inchi, has_smiles

__all__ = [
    "ChEMBLCompoundGetter",
]

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


class ChEMBLCompoundGetter(Obo):
    """An ontology representation of ChEMBL compounds."""

    ontology = "chembl.compound"
    bioversions_key = "chembl"
    typedefs = [exact_match]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Return ChEMBL Compounds as OBO."""
    return ChEMBLCompoundGetter(force=force)


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
                    term.append_property(has_smiles, smiles)
                if inchi:
                    term.append_property(has_inchi, inchi)
                if inchi_key:
                    term.append_exact_match(Reference(prefix="inchikey", identifier=inchi_key))
                yield term


if __name__ == "__main__":
    ChEMBLCompoundGetter.cli()
