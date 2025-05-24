"""High-level ontology object model."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from curies import Converter
from rdflib import OWL, RDF, Graph, term

from pyobo.struct.functional.dsl import Annotation, Annotations, Axiom, Box
from pyobo.struct.functional.utils import (
    EXAMPLE_ONTOLOGY_IRI,
    FunctionalOWLSerializable,
    list_to_funowl,
)
from pyobo.utils.io import safe_open

__all__ = [
    "Document",
    "Import",
    "Ontology",
    "Prefix",
    "write_ontology",
]


def write_ontology(
    *,
    prefixes: dict[str, str] | list[Prefix],
    iri: str | None = None,
    version_iri: str | None = None,
    directly_imports_documents: list[Import | str] | None = None,
    annotations: Annotations | None = None,
    axioms: list[Axiom] | None = None,
    file=None,
) -> None:
    """Print an ontology serialized as functional OWL."""
    ontology = Ontology(
        iri=iri,
        version_iri=version_iri,
        directly_imports_documents=directly_imports_documents,
        annotations=annotations,
        axioms=axioms,
    )
    document = Document(ontology, prefixes)
    print(document.to_funowl(), file=file)


class Document:
    """Represents a functional OWL document."""

    prefixes: list[Prefix]
    ontologies: list[Ontology]

    def __init__(
        self,
        ontologies: Ontology | list[Ontology],
        prefixes: dict[str, str] | list[Prefix],
    ) -> None:
        """Initialize a functional OWL document.

        :param ontologies: An ontology or list of ontologies.

            .. warning::

                RDF export can only be used for a single ontology.

        :param prefixes: A list of prefixes to define in the document

            .. seealso::

                `3.7 "Functional-Style Syntax"
                <https://www.w3.org/TR/owl2-syntax/#Functional-Style_Syntax>`_
        """
        self.ontologies = ontologies if isinstance(ontologies, list) else [ontologies]
        if isinstance(prefixes, dict):
            self.prefixes = [
                Prefix(prefix, uri_prefix)
                for prefix, uri_prefix in sorted(prefixes.items(), key=lambda kv: kv[0].casefold())
            ]
        else:
            self.prefixes = prefixes

    @property
    def prefix_map(self) -> dict[str, str]:
        """Get a simple dictionary representation of prefixes."""
        return {prefix.prefix: prefix.uri_prefix for prefix in self.prefixes}

    def write_rdf(self, path: str | Path) -> None:
        """Write RDF to a file."""
        path = Path(path).expanduser().resolve()
        graph = self.to_rdf()
        graph.serialize(path, format="ttl")

    def to_rdf(self) -> Graph:
        """Get an RDFlib graph representing the ontology."""
        if len(self.ontologies) != 1:
            raise ValueError("Can only export one ontology to RDF")
        graph = Graph()
        for prefix_box in self.prefixes:
            graph.namespace_manager.bind(prefix_box.prefix, prefix_box.uri_prefix)
        converter = Converter.from_rdflib(graph)
        for ontology in self.ontologies:
            ontology.to_rdflib_node(graph, converter)
        return graph

    def write_funowl(self, path: str | Path) -> None:
        """Write functional OWL to a file.."""
        path = Path(path).expanduser().resolve()
        with safe_open(path, read=False) as file:
            file.write(self.to_funowl())

    def to_funowl(self) -> str:
        """Get the document as a functional OWL string."""
        prefixes = list_to_funowl(self.prefixes, sep="\n")
        ontologies = list_to_funowl(self.ontologies, sep="\n\n")
        return prefixes + "\n\n" + ontologies


class Ontology(Box):
    """Represents an OWL 2 ontology defined in `3 "Ontologies" <https://www.w3.org/TR/owl2-syntax/#Ontologies>`_."""

    directly_imports_documents: Sequence[Import]
    annotations: Sequence[Annotation]
    axioms: Sequence[Box]

    def __init__(
        self,
        iri: str | None = None,
        version_iri: str | None = None,
        directly_imports_documents: list[Import | str] | None = None,
        annotations: Annotations | None = None,
        axioms: Sequence[Box] | None = None,
    ) -> None:
        """Instantiate an ontology.

        :param iri: The ontology IRI.

            .. seealso::

                `3.1 "Ontology IRI and Version IRI"
                <https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI>`_

        :param version_iri: An optional version IRI
        :param directly_imports_documents: Optional ontology imports

            .. seealso::

                `3.4 "Imports" <https://www.w3.org/TR/owl2-syntax/#Imports>`_

        :param annotations: .. seealso::

            `3.5 "Ontology Annotations"
            <https://www.w3.org/TR/owl2-syntax/#Ontology_Annotations>`_
        :param axioms: statements about what is true in the domain

            .. seealso::

                `9 "Axioms" <https://www.w3.org/TR/owl2-syntax/#Axioms>`_
        """
        self.iri = iri
        self.version_iri = version_iri
        self.directly_imports_documents = [
            Import(i) if isinstance(i, str) else i for i in directly_imports_documents or []
        ]
        self.annotations = annotations or []
        self.axioms = axioms or []
        # this is the amount of leading whitespace on each
        # when outputting to functional OWL
        self._leading = ""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.URIRef | term.BNode:
        """Add the ontology to the triple store."""
        ontology_node = term.URIRef(self.iri) if self.iri is not None else term.BNode()
        graph.add((ontology_node, RDF.type, OWL.Ontology))
        if self.version_iri:
            graph.add((ontology_node, OWL.versionIRI, term.URIRef(self.version_iri)))
        for imp in self.directly_imports_documents:
            graph.add((ontology_node, OWL.imports, term.URIRef(imp.iri)))
        for annotation in self.annotations:
            annotation._add_to_triple(graph, ontology_node, converter=converter)
        for axiom in self.axioms:
            axiom.to_rdflib_node(graph, converter)
        return ontology_node

    def to_funowl(self) -> str:
        """Make functional OWL."""
        tag = self.__class__.__name__
        return f"{tag}({self.to_funowl_args()}\n)"

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the ontology."""
        rv = ""
        if self.iri:
            rv += f"<{self.iri}>"
            if self.version_iri:
                rv += f" <{self.version_iri}>"
        rv += f"\n{self._leading}"

        parts: list[Sequence[FunctionalOWLSerializable]] = []
        if self.directly_imports_documents:
            parts.append(self.directly_imports_documents)
        if self.annotations:
            parts.append(self.annotations)
        if self.axioms:
            parts.append(self.axioms)

        rv += f"\n\n{self._leading}".join(
            list_to_funowl(part, sep=f"\n{self._leading}") for part in parts
        )
        return rv


class Prefix(Box):
    """A model for imports, as defined by `3.7 "Functional-Style Syntax" <https://www.w3.org/TR/owl2-syntax/#Functional-Style_Syntax>`_."""

    def __init__(self, prefix: str, uri_prefix: str) -> None:
        """Initialize the definition with a CURIE prefix and URI prefix."""
        self.prefix = prefix
        self.uri_prefix = uri_prefix

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.BNode:
        """Add the prefix to an RDF graph."""
        graph.namespace_manager.bind(self.prefix, self.uri_prefix)
        return term.BNode()  # dummy

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the prefix."""
        return f"{self.prefix}:=<{self.uri_prefix}>"


class Import(Box):
    """A model for imports, as defined by `3.4 "Imports" <https://www.w3.org/TR/owl2-syntax/#Imports>`_."""

    def __init__(self, iri: str) -> None:
        """Initialize the import."""
        self.iri = iri

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.BNode:
        """Add the import to an RDF graph."""
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the import."""
        return f"<{self.iri}>"


def get_rdf_graph_oracle(boxes: list[Box], *, prefix_map: dict[str, str]) -> Graph:
    """Serialize to turtle via OFN and conversion with ROBOT."""
    import bioontologies.robot

    ontology = Ontology(
        iri=EXAMPLE_ONTOLOGY_IRI,
        axioms=boxes,
    )
    document = Document(ontology, prefix_map)
    graph = Graph()
    with tempfile.TemporaryDirectory() as directory:
        stub = Path(directory).joinpath("test")
        ofn_path = stub.with_suffix(".ofn")
        text = document.to_funowl()
        ofn_path.write_text(text)
        ttl_path = stub.with_suffix(".ttl")
        try:
            bioontologies.robot.convert(ofn_path, ttl_path)
        except subprocess.CalledProcessError:
            raise RuntimeError(f"failed to convert axioms from:\n\n{text}") from None
        graph.parse(ttl_path)
    return graph
