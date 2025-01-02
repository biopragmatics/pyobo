"""Utilities for functional OWL."""

from __future__ import annotations

from abc import ABC, abstractmethod

from curies import Converter
from rdflib import Graph, term

__all__ = [
    "FunctionalOWLSerializable",
    "RDFNodeSerializable",
]


class FunctionalOWLSerializable(ABC):
    """An object that can be serialized to functional OWL."""

    def to_funowl(self) -> str:
        """Make functional OWL."""
        tag = self.__class__.__name__
        return f"{tag}( {self.to_funowl_args()} )"

    @abstractmethod
    def to_funowl_args(self) -> str:
        """Make a string representing the positional arguments inside a box."""


class RDFNodeSerializable(ABC):
    """An object that can be serialized to RDF as a node."""

    @abstractmethod
    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
        """Make RDF."""
