"""Get compartments from BiGG."""

from collections.abc import Iterable

from bioversions.utils import get_soup

from pyobo import Obo, Reference, Term

__all__ = [
    "BiGGCompartmentGetter",
    "get_compartments",
]

DATA_URL = "http://bigg.ucsd.edu/compartments/"
PREFIX = "bigg.compartment"
GO_MAPPING: dict[str, Reference | None] = {
    "c": Reference(prefix="go", identifier="0005829", name="cytosol"),
    "e": Reference(prefix="go", identifier="0005615", name="extracellular space"),
    "p": Reference(prefix="go", identifier="0042597", name="periplasmic space"),
    "m": Reference(prefix="go", identifier="0005739", name="mitochondrion"),
    "r": Reference(prefix="go", identifier="0005783", name="endoplasmic reticulum"),
    "v": Reference(prefix="go", identifier="0005773", name="vacuole"),
    "n": Reference(prefix="go", identifier="0005634", name="nucleus"),
    "g": Reference(prefix="go", identifier="0005794", name="Golgi apparatus"),
    "u": Reference(prefix="go", identifier="0009579", name="thylakoid"),
    "l": Reference(prefix="go", identifier="0005764", name="lysosome"),
    "h": Reference(prefix="go", identifier="0009507", name="chloroplast"),
    "f": Reference(prefix="go", identifier="0005929", name="cilium"),
    "s": Reference(prefix="go", identifier="1990413", name="eyespot apparatus"),
    "um": Reference(prefix="go", identifier="0042651", name="thylakoid membrane"),
    "y": Reference(prefix="go", identifier="0070069", name="cytochrome complex"),
    # note that glyoxysome is a child class of peroxisome in GO
    "x": Reference(prefix="go", identifier="0005777", name="peroxisome"),
    "mm": Reference(prefix="go", identifier="0005743", name="mitochondrial inner membrane"),
    "im": Reference(prefix="go", identifier="0005758", name="mitochondrial intermembrane space"),
    "cx": None,  # missing for carboxyzome
    "cm": None,  # missing for cytosolic membrane
    "i": None,  # missing for inner mitochondrial compartment
    "w": None,  # missing for wildtype staph aureus
}


class BiGGCompartmentGetter(Obo):
    """An ontology representation of BiGG compartments."""

    ontology = PREFIX
    bioversions_key = "bigg"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_terms(force=force, version=self._version_or_raise)


def get_compartments(*, force: bool = False, version: str | None = None) -> dict[str, str]:
    """Get a dictionary of BiGG compartments."""
    rv = {}
    soup = get_soup(DATA_URL)
    table = soup.find(**{"class": "myTable"})  # type:ignore[arg-type]
    if table is None:
        raise ValueError
    for row in table.find_all("tr"):  # type:ignore[attr-defined]
        cells = list(row.find_all("td"))
        if not cells:
            continue
        identifier_cell, name_cell = cells
        rv[identifier_cell.text] = name_cell.text
    return rv


def iterate_terms(*, force: bool = False, version: str | None = None) -> Iterable[Term]:
    """Iterate over BiGG compartments."""
    compartments = get_compartments(force=force, version=version)
    for identifier, name in compartments.items():
        term = Term.from_triple(PREFIX, identifier, name)
        if go_component_ref := GO_MAPPING.get(identifier):
            term.append_exact_match(go_component_ref)
        yield term


if __name__ == "__main__":
    BiGGCompartmentGetter.cli()
