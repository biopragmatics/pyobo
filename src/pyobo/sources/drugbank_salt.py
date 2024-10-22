"""Convert DrugBank Salts to OBO.

Run with ``python -m pyobo.sources.drugbank_salt``

Get relations between drugbank salts and drugbank parents with
``pyobo relations drugbank --relation obo:has_salt`` or

.. code-block:: python

    import pyobo

    df = pyobo.get_filtered_relations_df("drugbank", "obo:has_salt")
"""

import logging
from collections.abc import Iterable

from .drugbank import iterate_drug_info
from ..struct import Obo, Reference, Term

__all__ = [
    "DrugBankSaltGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "drugbank.salt"


class DrugBankSaltGetter(Obo):
    """A getter for DrugBank Salts."""

    ontology = PREFIX
    bioversions_key = "drugbank"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get DrugBank Salts as OBO."""
    return DrugBankSaltGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over DrugBank Salt terms in OBO."""
    for drug_info in iterate_drug_info(version, force=force):
        for salt in drug_info.get("salts", []):
            xrefs = []
            for key in ["unii", "cas", "inchikey"]:
                identifier = salt.get(key)
                if identifier:
                    xrefs.append(Reference(prefix=key, identifier=identifier))

            yield Term(
                reference=Reference(
                    prefix=PREFIX,
                    identifier=salt["identifier"],
                    name=salt["name"],
                ),
                xrefs=xrefs,
            )


if __name__ == "__main__":
    DrugBankSaltGetter.cli()
