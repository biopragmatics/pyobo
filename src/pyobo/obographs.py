"""Convert PyOBO into OBO Graph."""

from typing import List

import bioregistry
from bioontologies.obograph import Definition, Edge, Meta, Node, Synonym, Xref
from bioontologies.robot import Graph, GraphDocument, ParseResults

from pyobo.struct import Obo, Term

__all__ = [
    "parse_results_from_obo",
]


def parse_results_from_obo(obo: Obo) -> ParseResults:
    """Get parse results from an OBO graph."""
    graph = graph_from_obo(obo)
    return ParseResults(graph_document=GraphDocument(graphs=[graph]))


def graph_from_obo(obo: Obo) -> Graph:
    """Get an OBO Graph object from a PyOBO object."""
    nodes: List[Node] = []
    edges: List[Edge] = []
    for term in obo:
        nodes.append(_get_class_node(term))
        edges.extend(_get_edges(term))
    return Graph(
        id=bioregistry.get_bioregistry_iri("bioregistry", obo.ontology),
        prefix=obo.ontology,
        meta=_get_meta(obo),
        nodes=nodes,
        edges=edges,
        standardized=True,  # from construction :)
    )


def _get_meta(obo: Obo) -> Meta:
    return Meta()


def _get_class_node(term: Term) -> Node:
    if not term.definition:
        definition = None
    else:
        definition = Definition(val=term.definition, xrefs=[p.curie for p in term.provenance])
    xrefs = [
        Xref(
            val=xref.bioregistry_link,
            # FIXME
            prefix=xref.prefix,
            identifier=xref.identifier,
            standardized=True,
        )
        for xref in term.xrefs
    ]
    synonyms = [
        Synonym(
            val=synonym.name,
            pred=synonym.type.id if synonym.type else None,
            synonymType=synonym.specificity,
            standardized=True,
            xrefs=[x.curie for x in synonym.provenance],
        )
        for synonym in term.synonyms
    ]

    meta = Meta(
        definition=definition,
        xrefs=xrefs,
        synonyms=synonyms,
        version=None,  # TODO get from ontology
        basicPropertyValues=None,  # TODO properties
        deprecated=term.is_obsolete or False,
    )
    return Node(
        id=term.bioregistry_link,
        lbl=term.name,
        meta=meta,
        type="CLASS",
        prefix=term.prefix,
        luid=term.identifier,
        standardized=True,
    )


def _get_edges(term: Term) -> List[Edge]:
    rv = []
    for typedef, targets in term.relationships.items():
        for target in targets:
            rv.append(
                Edge(
                    sub=term.curie,
                    pred=typedef.curie,
                    obj=target.curie,
                )
            )
    return rv
