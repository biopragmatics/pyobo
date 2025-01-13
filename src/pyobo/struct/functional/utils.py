"""Utilities for functional OWL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

import curies
import rdflib
from curies import Converter, Reference
from rdflib import OWL, RDF, Graph, term

from pyobo.constants import DEFAULT_PREFIX_MAP

__all__ = [
    "EXAMPLE_PREFIX_MAP",
    "FunctionalOWLSerializable",
    "RDFNodeSerializable",
    "get_rdf_graph",
]


EXAMPLE_PREFIX_MAP = {
    **DEFAULT_PREFIX_MAP,
    "oboInOwl": "http://www.geneontology.org/formats/oboInOwl#",
    "dcterms": "http://purl.org/dc/terms/",
    "obo": "http://purl.obolibrary.org/obo/",
    "OMO": "http://purl.obolibrary.org/obo/OMO_",
    "sssom": "https://w3id.org/sssom/",
    "semapv": "https://w3id.org/semapv/vocab/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    #
    "a": "https://example.org/a:",
    "orcid": "https://orcid.org",
    "ZFA": "http://purl.obolibrary.org/obo/ZFA_",
    "CL": "http://purl.obolibrary.org/obo/CL_",
    "BFO": "http://purl.obolibrary.org/obo/BFO_",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
}


class FunctionalOWLSerializable(ABC):
    """An object that can be serialized to functional OWL."""

    def to_funowl(self) -> str:
        """Make functional OWL."""
        tag = self.__class__.__name__
        return f"{tag}({self.to_funowl_args()})"

    @abstractmethod
    def to_funowl_args(self) -> str:
        """Make a string representing the positional arguments inside a box."""


class RDFNodeSerializable(ABC):
    """An object that can be serialized to RDF as a node."""

    @abstractmethod
    def to_rdflib_node(self, graph: Graph, converter: Converter):
        """Make RDF."""

    def to_ttl(self, prefix_map: dict[str, str], *, output_prefixes: bool = False) -> str:
        """Output terse Turtle statements."""
        return serialize_turtle([self], output_prefixes=output_prefixes, prefix_map=prefix_map)


EXAMPLE_ONTOLOGY_IRI = "https://example.org/example.ofn"


def get_rdf_graph(
    axioms: Iterable[RDFNodeSerializable], prefix_map: dict[str, str]
) -> rdflib.Graph:
    """Serialize axioms as an RDF graph."""
    graph = Graph()
    graph.add((term.URIRef(EXAMPLE_ONTOLOGY_IRI), RDF.type, OWL.Ontology))
    # chain these together so you don't have to worry about
    # default namespaces like owl
    converter = curies.chain(
        [
            Converter.from_rdflib(graph),
            Converter.from_prefix_map(prefix_map),
        ]
    )
    for prefix, uri_prefix in converter.bimap.items():
        graph.namespace_manager.bind(prefix, uri_prefix)
    for axiom in axioms:
        axiom.to_rdflib_node(graph, converter)
    return graph


def serialize_turtle(
    axioms: Iterable[RDFNodeSerializable],
    *,
    output_prefixes: bool = False,
    prefix_map: dict[str, str],
) -> str:
    """Serialize axioms as turtle."""
    graph = get_rdf_graph(axioms, prefix_map=prefix_map)
    rv = graph.serialize()
    if output_prefixes:
        return rv.strip()
    return "\n".join(line for line in rv.splitlines() if not line.startswith("@prefix")).strip()


def list_to_funowl(
    elements: Iterable[FunctionalOWLSerializable | Reference], *, sep: str = " "
) -> str:
    """Serialize a list of objects as functional OWL, separated by space or other givne separator."""
    return sep.join(
        element.to_funowl() if isinstance(element, FunctionalOWLSerializable) else element.curie
        for element in elements
    )
