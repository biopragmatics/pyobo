"""Converter for OMIM Phenotypic Series."""

import logging
from collections.abc import Iterable

from bioversions.utils import get_soup

from pyobo.struct import Obo, Term

__all__ = [
    "OMIMPSGetter",
]

logger = logging.getLogger(__name__)
PREFIX = "omim.ps"
URL = "https://omim.org/phenotypicSeriesTitles/"


class OMIMPSGetter(Obo):
    """An ontology representation of OMIM Phenotypic Series."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        soup = get_soup(URL, user_agent="Mozilla/5.0")
        content = soup.find(id="mimContent")
        if content is None:
            raise ValueError("omim.ps failed - scraper could not find id='mimContent' in HTML")
        table = content.find("table")  # type:ignore[attr-defined]
        if table is None:
            raise ValueError("omim.ps failed - scraper could not find table in HTML")
        tbody = table.find("tbody")
        if tbody is None:
            raise ValueError("omim.ps failed - scraper could not find table body in HTML")
        for row in tbody.find_all("tr"):
            anchor = row.find("td").find("a")
            name = anchor.text.strip()
            identifier = anchor.attrs["href"][len("/phenotypicSeries/") :]
            yield Term.from_triple(PREFIX, identifier, name)


if __name__ == "__main__":
    OMIMPSGetter.cli()
