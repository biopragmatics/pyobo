"""Gene Ontology."""

from pyobo import get_descendants

__all__ = [
    "is_biological_process",
    "is_cellular_component",
    "is_molecular_function",
]


def is_biological_process(identifier: str) -> bool:
    """Return if the given GO identifier is a biological process.

    :param identifier: A local unique identifier from GO
    :return: If the identifier is a biological process

    >>> is_biological_process("0006915")
    True
    >>> is_biological_process("GO:0006915")
    True
    """
    return _is_descendant(identifier, "0008150")


def is_molecular_function(identifier: str) -> bool:
    """Return if the given GO identifier is a molecular function.

    :param identifier: A local unique identifier from GO
    :return: If the identifier is a molecular function

    >>> is_molecular_function("0006915")
    False
    """
    return _is_descendant(identifier, "0003674")


def is_cellular_component(identifier: str) -> bool:
    """Return if the given GO identifier is a cellular component.

    :param identifier: A local unique identifier from GO
    :return: If the identifier is a cellular component

    >>> is_cellular_component("0006915")
    False
    """
    return _is_descendant(identifier, "0005575")


def _is_descendant(identifier: str, ancestor: str) -> bool:
    identifier = identifier.lower()
    if not identifier.startswith("go:"):
        identifier = f"go:{identifier}"
    descendants = get_descendants("go", ancestor)
    return descendants is not None and identifier in descendants
