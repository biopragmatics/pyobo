"""Gene Ontology."""

from pyobo import get_descendants

__all__ = [
    "is_biological_process",
    "is_molecular_function",
    "is_cellular_component",
]


def is_biological_process(identifier: str) -> bool:
    """Return if the given GO identifier is a biological process.

    >>> is_biological_process("0006915")
    True
    >>> is_biological_process("GO:0006915")
    True
    >>> is_molecular_function("0006915")
    False
    >>> is_cellular_component("0006915")
    False
    """
    return _is_descendant(identifier, "0008150")


def is_molecular_function(identifier: str) -> bool:
    """Return if the given GO identifier is a molecular function."""
    return _is_descendant(identifier, "0003674")


def is_cellular_component(identifier: str) -> bool:
    """Return if the given GO identifier is a cellular component."""
    return _is_descendant(identifier, "0005575")


def _is_descendant(identifier: str, ancestor: str) -> bool:
    identifier = identifier.lower()
    if not identifier.startswith("go:"):
        identifier = f"go:{identifier}"
    descendants = get_descendants("go", ancestor)
    return descendants is not None and identifier in descendants


if __name__ == "__main__":
    import doctest

    doctest.testmod()
