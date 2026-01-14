"""Converter for models in BiGG."""

import json
import logging
from collections.abc import Iterable

from pyobo.resources.ncbitaxon import get_ncbitaxon_id
from pyobo.struct import Obo, Term
from pyobo.utils.path import ensure_path

__all__ = [
    "BiGGModelGetter",
]

logger = logging.getLogger(__name__)
URL = "http://bigg.ucsd.edu/api/v2/models"
PREFIX = "bigg.model"


class BiGGModelGetter(Obo):
    """An ontology representation of BiGG Models."""

    ontology = PREFIX
    bioversions_key = "bigg"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_terms(version=self._version_or_raise)


def iterate_terms(version: str) -> Iterable[Term]:
    """Iterate over BiGG Models."""
    path = ensure_path(PREFIX, url=URL, version=version)
    records = json.loads(path.read_text())["results"]
    for record in records:
        ncbitaxon_id = get_ncbitaxon_id(record["organism"])
        term = Term.from_triple(PREFIX, record["bigg_id"])
        if ncbitaxon_id:
            term.set_species(ncbitaxon_id)
        else:
            logger.info("[%s] could not ground organism name: %s", term.curie, record["organism"])
        yield term


if __name__ == "__main__":
    BiGGModelGetter.cli()
