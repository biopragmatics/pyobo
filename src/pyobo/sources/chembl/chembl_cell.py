"""Converter for ChEMBL cells."""

import logging
from collections.abc import Iterable

import chembl_downloader

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import derives_from_organism, exact_match

__all__ = [
    "ChEMBLCellGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "chembl.cell"


class ChEMBLCellGetter(Obo):
    """An ontology representation of ChEMBL cells."""

    ontology = PREFIX
    bioversions_key = "chembl"
    typedefs = [exact_match, derives_from_organism]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


QUERY = """\
SELECT
    CHEMBL_ID,
    CELL_NAME,
    CELL_DESCRIPTION,
    CELL_SOURCE_TISSUE,
    CELL_SOURCE_TAX_ID,
    CLO_ID,
    EFO_ID,
    CELLOSAURUS_ID,
    CL_LINCS_ID,
    CELL_ONTOLOGY_ID
FROM CELL_DICTIONARY
"""


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over ChEMBL cell terms."""
    with chembl_downloader.cursor(version=version) as cursor:
        cursor.execute(QUERY)
        for (
            chembl_id,
            name,
            desc,
            _source_tissue,
            taxid,
            clo,
            efo,
            cellosaurus,
            lincs,
            cl,
        ) in cursor.fetchall():
            term = Term(
                reference=Reference(prefix=PREFIX, identifier=chembl_id, name=name),
                definition=desc if desc and desc != name else None,
            )
            if taxid:
                term.append_relationship(
                    derives_from_organism, Reference(prefix="ncbitaxon", identifier=taxid)
                )
            # TODO how to annotate tissue, via TISSUE_DICTIONARY
            if clo:
                term.append_exact_match(
                    Reference(prefix="clo", identifier=clo.removeprefix("CLO_"))
                )
            if efo:
                term.append_exact_match(
                    Reference(prefix="efo", identifier=efo.removeprefix("EFO_").removeprefix("EFO"))
                )
            if cellosaurus:
                term.append_exact_match(
                    Reference(prefix="cellosaurus", identifier=cellosaurus.removeprefix("CVCL_"))
                )
            if lincs:
                # with LCL- included!
                term.append_exact_match(Reference(prefix="lincs.cell", identifier=lincs))
            if cl:
                term.append_exact_match(Reference(prefix="cl", identifier=cl.removeprefix("CL_")))
            yield term


if __name__ == "__main__":
    ChEMBLCellGetter.cli()
