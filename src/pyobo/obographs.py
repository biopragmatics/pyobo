"""Convert PyOBO into OBO Graph."""

from collections.abc import Iterable

import bioregistry
import curies
from bioontologies.obograph import (
    OBO_SYNONYM_TO_OIO,
    OIO_TO_REFERENCE,
    Definition,
    Edge,
    Graph,
    GraphDocument,
    Meta,
    Node,
    Synonym,
    Xref,
)
from bioontologies.robot import ParseResults
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import definition_source, is_a

__all__ = [
    "graph_from_obo",
    "parse_results_from_obo",
]


def parse_results_from_obo(obo: Obo) -> ParseResults:
    """Get parse results from an OBO graph."""
    graph = graph_from_obo(obo)
    return ParseResults(graph_document=GraphDocument(graphs=[graph]))


def graph_from_obo(obo: Obo, use_tqdm: bool = True) -> Graph:
    """Get an OBO Graph object from a PyOBO object."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    for term in tqdm(
        obo, disable=not use_tqdm, unit="term", unit_scale=True, desc=f"[{obo.ontology}] to JSON"
    ):
        nodes.append(_get_class_node(term))
        edges.extend(_iter_edges(term))
    return Graph(
        id=bioregistry.get_bioregistry_iri("bioregistry", obo.ontology),
        prefix=obo.ontology,
        meta=_get_meta(obo),
        nodes=nodes,
        edges=edges,
        standardized=True,  # from construction :)
    )


def _get_meta(obo: Obo) -> Meta:
    return Meta(
        version=obo.data_version,
    )


def _rewire(r: Reference) -> curies.Reference:
    return curies.Reference(prefix=r.prefix, identifier=r.identifier)


def _get_class_node(term: Term) -> Node:
    if term.definition or term.provenance:
        definition = Definition.from_parsed(
            value=term.definition, references=[_rewire(p) for p in term.provenance]
        )
    else:
        definition = None

    if term.xrefs:
        if not term.xref_types:
            term.xref_types = [
                Reference(prefix="oboInOwl", identifier="hasDbXref") for _ in term.xrefs
            ]
        elif len(term.xrefs) != len(term.xref_types):
            raise ValueError

    xrefs = [
        Xref.from_parsed(
            predicate=_rewire(xref_type),
            value=_rewire(xref),
        )
        for xref, xref_type in zip(term.xrefs, term.xref_types)
    ]
    default_st = Reference(prefix="oboInOwl", identifier="SynonymType")
    synonyms = [
        Synonym.from_parsed(
            name=synonym.name,
            predicate=OIO_TO_REFERENCE[OBO_SYNONYM_TO_OIO[synonym.specificity]],
            synonym_type=_rewire(synonym.type.reference) if synonym.type else default_st,
            references=[_rewire(x) for x in synonym.provenance],
        )
        for synonym in term.synonyms
    ]

    meta = Meta(
        definition=definition,
        xrefs=xrefs,
        synonyms=synonyms,
        basicPropertyValues=None,  # TODO properties
        deprecated=term.is_obsolete or False,
    )
    return Node(
        id=term.bioregistry_link,
        lbl=term.name,
        meta=meta,
        type="CLASS",
        reference=_rewire(term.reference),
        standardized=True,
    )


def _iter_edges(term: Term) -> Iterable[Edge]:
    for parent in term.parents:
        yield Edge.from_parsed(
            _rewire(term.reference),
            _rewire(is_a.reference),
            _rewire(parent),
        )

    for typedef, targets in term.relationships.items():
        for target in targets:
            yield Edge.from_parsed(
                _rewire(term.reference),
                _rewire(typedef.reference),
                _rewire(target),
            )

    for provenance_reference in term.provenance:
        yield Edge.from_parsed(
            _rewire(term.reference),
            _rewire(definition_source.reference),
            _rewire(provenance_reference),
        )
    # TODO also look through xrefs and seealso to get provenance xrefs?
