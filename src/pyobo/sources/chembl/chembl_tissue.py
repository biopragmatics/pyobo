"""Converter for ChEMBL tissues."""

import logging
from collections.abc import Iterable

import chembl_downloader

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import exact_match

__all__ = [
    "ChEMBLTissueGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "chembl.tissue"
QUERY = """\
SELECT
    CHEMBL_ID,
    PREF_NAME,
    UBERON_ID,
    EFO_ID,
    BTO_ID,
    CALOHA_ID
FROM TISSUE_DICTIONARY
"""


class ChEMBLTissueGetter(Obo):
    """An ontology representation of ChEMBL tissues."""

    ontology = PREFIX
    bioversions_key = "chembl"
    typedefs = [exact_match]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over ChEMBL tissue terms."""
    with chembl_downloader.cursor(version=version) as cursor:
        cursor.execute(QUERY)
        for chembl_id, name, uberon, efo, bto, caloha in cursor.fetchall():
            term = Term(
                reference=Reference(prefix=PREFIX, identifier=chembl_id, name=name),
            )
            if uberon:
                term.append_exact_match(
                    Reference(prefix="uberon", identifier=uberon.removeprefix("UBERON:"))
                )
            if efo:
                term.append_exact_match(
                    Reference(
                        prefix="efo", identifier=efo.removeprefix("EFO:").removeprefix("EFO;")
                    )
                )
            if bto:
                term.append_exact_match(
                    Reference(prefix="bto", identifier=bto.removeprefix("BTO:"))
                )
            if caloha:
                term.append_exact_match(Reference(prefix="caloha", identifier=caloha))
            yield term


if __name__ == "__main__":
    ChEMBLTissueGetter.cli()
