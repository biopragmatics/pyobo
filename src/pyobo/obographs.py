"""Convert PyOBO into OBO Graph."""

from typing import List, Optional

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

from pyobo.struct import Obo, Reference, Term

__all__ = [
    "graph_from_obo",
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
    return Meta(
        version=obo.data_version,
    )


def _rewire(r: Reference) -> curies.Reference:
    return curies.Reference(prefix=r.prefix, identifier=r.identifier)


def _get_class_node(term: Term) -> Node:
    if not term.definition:
        definition = None
    else:
        definition = Definition(value=term.definition, xrefs=[p.curie for p in term.provenance])

    if term.xrefs:
        if not term.xref_types:
            term.xref_types = [
                Reference(prefix="oboInOwl", identifier="hasDbXref") for _ in term.xrefs
            ]
        elif len(term.xrefs) != len(term.xref_types):
            raise ValueError

    xrefs = [
        Xref(
            val=xref.bioregistry_link,
            value=_rewire(xref),
            predicate_raw=xref_type.curie,
            predicate=_rewire(xref_type),
            standardized=True,
        )
        for xref, xref_type in zip(term.xrefs, term.xref_types)
    ]
    default_st = Reference(prefix="oboInOwl", identifier="SynonymType")
    synonyms = [
        Synonym(
            val=synonym.name,
            predicate_raw=OBO_SYNONYM_TO_OIO[synonym.specificity],
            predicate=OIO_TO_REFERENCE[OBO_SYNONYM_TO_OIO[synonym.specificity]],
            synonym_type_raw=synonym.type.curie if synonym.type else "oboInOwl:SynonymType",
            synonym_type=_rewire(synonym.type.reference) if synonym.type else default_st,
            standardized=True,
            xrefs_raw=[x.curie for x in synonym.provenance],
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
        reference=curies.Reference(
            prefix=term.prefix,
            identifier=term.identifier,
        ),
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
