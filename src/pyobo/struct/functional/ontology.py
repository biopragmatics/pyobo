"""High-level ontology object model."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from curies import Converter
from rdflib import Graph, term

from pyobo.struct.functional.dsl import Annotations, Axiom, Box
from pyobo.struct.functional.utils import EXAMPLE_ONTOLOGY_IRI

__all__ = [
    "Import",
    "Ontology",
    "Prefix",
    "write_ontology",
]


def write_ontology(
    *,
    prefixes: dict[str, str],
    iri: str,
    version_iri: str | None = None,
    directly_imports_documents: list[Import] | None = None,
    annotations: Annotations | None = None,
    axioms: list[Axiom] | None = None,
    file=None,
) -> None:
    """Print an ontology serialized as functional OWL."""
    ontology = Ontology(
        prefixes=prefixes,
        iri=iri,
        version_iri=version_iri,
        directly_imports_documents=directly_imports_documents,
        annotations=annotations,
        axioms=axioms,
    )
    print(ontology.to_funowl(), file=file)


class Ontology(Box):
    """Represents an OWL 2 ontology defined in `3 "Ontologies" <https://www.w3.org/TR/owl2-syntax/#Ontologies>`_."""

    def __init__(
        self,
        prefixes: dict[str, str],
        iri: str,
        version_iri: str | None = None,
        directly_imports_documents: list[Import] | None = None,
        annotations: Annotations | None = None,
        axioms: list[Axiom] | None = None,
    ) -> None:
        """Instantiate an ontology.

        :param prefixes: A list of prefixes to define in the document

            .. seealso:: `3.7 "Functional-Style Syntax" <https://www.w3.org/TR/owl2-syntax/#Functional-Style_Syntax>`_
        :param iri: The ontology IRI.

            .. seealso:: `3.1 "Ontology IRI and Version IRI" <https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI>`_
        :param version_iri: An optional version IRI
        :param directly_imports_documents:

            .. seealso:: `3.4 "Imports" <https://www.w3.org/TR/owl2-syntax/#Imports>`_
        :param annotations:

            .. seealso:: `3.5 "Ontology Annotations" <https://www.w3.org/TR/owl2-syntax/#Ontology_Annotations>`_
        :param axioms: statements about what is true in the domain

            .. seealso:: `9 "Axioms" <https://www.w3.org/TR/owl2-syntax/#Axioms>`_
        """
        self.prefixes = prefixes
        self.iri = iri
        self.version_iri = version_iri
        self.directly_imports_documents = directly_imports_documents
        self.annotations = annotations
        self.axioms = axioms or []

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
        """Add the ontology to the triple store."""
        node = term.URIRef(self.iri)
        for axiom in self.axioms:
            axiom.to_rdflib_node(graph, converter)
        return node

    def to_funowl(self) -> str:
        """Serialize the ontology to a string containing functional OWL."""
        rv = "\n".join(
            f"Prefix({prefix}:=<{uri_prefix}>)" for prefix, uri_prefix in self.prefixes.items()
        )
        rv += f"\n\nOntology(<{self.iri}>"
        if self.version_iri:
            rv += f" <{self.version_iri}>"
        rv += "\n"
        rv += "\n".join(annotation.to_funowl() for annotation in self.annotations or [])
        rv += "\n"
        rv += "\n".join(axiom.to_funowl() for axiom in self.axioms or [])
        rv += "\n)"
        return rv

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the ontology."""
        raise RuntimeError


class Prefix(Box):
    """A model for imports, as defined by `3.7 "Functional-Style Syntax" <https://www.w3.org/TR/owl2-syntax/#Functional-Style_Syntax>`_."""

    def __init__(self, prefix: str, uri_prefix: str) -> None:
        """Initialize the definition with a CURIE prefix and URI prefix."""
        self.prefix = prefix
        self.uri_prefix = uri_prefix

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
        """Add the prefix to an RDF graph."""
        graph.namespace_manager.bind(self.prefix, self.uri_prefix)
        return term.BNode()  # dummy

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the prefix."""
        return f"{self.prefix}:={self.uri_prefix}"


class Import(Box):
    """A model for imports, as defined by `3.4 "Imports" <https://www.w3.org/TR/owl2-syntax/#Imports>`_."""

    def __init__(self, iri: str) -> None:
        """Initialize the import."""
        self.iri = iri

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
        """Add the import to an RDF graph."""
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the import."""
        return f" <{self.iri}> "


def get_rdf_graph_oracle(axioms: list[Axiom], *, prefix_map: dict[str, str]) -> Graph:
    """Serialize to turtle via OFN and conversion with ROBOT."""
    from bioontologies.robot import convert

    ontology = Ontology(
        iri=EXAMPLE_ONTOLOGY_IRI,
        prefixes=prefix_map,
        axioms=axioms,
    )
    graph = Graph()
    with tempfile.TemporaryDirectory() as directory:
        stub = Path(directory).joinpath("test")
        ofn_path = stub.with_suffix(".ofn")
        text = ontology.to_funowl()
        ofn_path.write_text(text)
        ttl_path = stub.with_suffix(".ttl")
        try:
            convert(ofn_path, ttl_path)
        except subprocess.CalledProcessError:
            raise RuntimeError(f"failed to convert axioms from:\n\n{text}") from None
        # turtle = ttl_path.read_text()
        graph.parse(ttl_path)

    return graph

    # turtle = "\n".join(
    #     line
    #     for line in turtle.splitlines()
    #     if line.strip() and not line.startswith("#") and not line.startswith("@prefix") and not line.startswith(
    #         "@base") and "owl:Ontology" not in line
    # )
    # return turtle
