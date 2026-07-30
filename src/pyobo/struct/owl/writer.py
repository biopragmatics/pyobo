"""Write OWL/XML."""

from __future__ import annotations

from pathlib import Path

from pyobo import Obo

__all__ = [
    "write_owl",
]


def write_owl(obo: Obo, path: str | Path) -> None:
    """Write OWL to a file."""
    raise NotImplementedError
