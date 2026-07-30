"""I/O for OWL."""

from .reader import read_owl
from .writer import write_owl

__all__ = [
    "read_owl",
    "write_owl",
]
