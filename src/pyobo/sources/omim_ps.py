# -*- coding: utf-8 -*-

"""Converter for OMIM Phenotypic Series."""

import logging
from typing import Iterable

from bioversions.utils import get_soup

from pyobo.struct import Obo, Term

__all__ = [
    "OMIMPSGetter",
]


logger = logging.getLogger(__name__)
PREFIX = "omim.ps"
URL = "https://omim.org/phenotypicSeriesTitles/all"


class OMIMPSGetter(Obo):
    """An ontology representation of OMIM Phenotypic Series."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        soup = get_soup(URL, user_agent="Mozilla/5.0")
        rows = soup.find(id="mimContent").find("table").find("tbody").find_all("tr")
        for row in rows:
            anchor = row.find("td").find("a")
            name = anchor.text.strip()
            identifier = anchor.attrs["href"][len("/phenotypicSeries/") :]
            yield Term.from_triple(PREFIX, identifier, name)


if __name__ == "__main__":
    OMIMPSGetter.cli()
