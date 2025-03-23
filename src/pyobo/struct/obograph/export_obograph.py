"""Convert PyOBO into OBO Graph."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import bioregistry
import curies
from bioontologies.obograph import (
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

from pyobo.struct import Obo, OBOLiteral, Reference, Referenced, Term
from pyobo.struct.typedef import definition_source, is_a

__all__ = [
    "graph_from_obo",
    "parse_results_from_obo",
]

logger = logging.getLogger(__name__)


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


def _rewire(r: curies.Reference | Referenced) -> curies.Reference:
    return curies.Reference(prefix=r.prefix, identifier=r.identifier)


def _get_class_node(term: Term) -> Node:
    if term.provenance or term.definition:
        definition = Definition.from_parsed(
            value=term.definition, references=_prep_prov(term.provenance)
        )
    else:
        definition = None
    xrefs = [
        Xref.from_parsed(
            predicate=_rewire(mapping_predicate),
            value=_rewire(mapping_object),
        )
        for mapping_predicate, mapping_object in term.get_mappings(
            include_xrefs=True, add_context=False
        )
    ]
    synonyms = [
        Synonym.from_parsed(
            name=synonym.name,
            predicate=synonym.predicate,
            synonym_type=_rewire(synonym.type) if synonym.type else None,
            references=_prep_prov(synonym.provenance),
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
        # FIXME do expansion same as for OFN
        id=f"https://bioregistry.io/{term.curie}",
        lbl=term.name,
        meta=meta,
        type="CLASS",
        reference=_rewire(term.reference),
        standardized=True,
    )


def _prep_prov(provenance):
    rv = []
    for x in provenance:
        match x:
            case Reference():
                rv.append(_rewire(x))
            case OBOLiteral():
                logger.debug("not implemented to convert literal provenance")
                continue
    return rv


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
                _rewire(typedef),
                _rewire(target),
            )

    for provenance_reference in term.provenance:
        if isinstance(provenance_reference, Reference):
            yield Edge.from_parsed(
                _rewire(term.reference),
                _rewire(definition_source.reference),
                _rewire(provenance_reference),
            )
    # TODO also look through xrefs and seealso to get provenance xrefs?
