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

from pyobo.struct import Obo, Referenced, Stanza, Term, TypeDef
from pyobo.struct.typedef import definition_source, is_a

__all__ = [
    "graph_from_obo",
    "parse_results_from_obo",
]

logger = logging.getLogger(__name__)


def parse_results_from_obo(obo_ontology: Obo) -> ParseResults:
    """Get parse results from an OBO graph."""
    graph = graph_from_obo(obo_ontology)
    return ParseResults(graph_document=GraphDocument(graphs=[graph]))


def graph_from_obo(obo_ontology: Obo, use_tqdm: bool = True) -> Graph:
    """Get an OBO Graph object from a PyOBO object."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    for term in tqdm(
        obo_ontology,
        disable=not use_tqdm,
        unit="term",
        unit_scale=True,
        desc=f"[{obo_ontology.ontology}] to JSON",
    ):
        nodes.append(_get_class_node(term))
        edges.extend(_get_stanza_edges(term))

    for typedef in obo_ontology.typedefs or []:
        nodes.append(_get_typedef_node(typedef))
        edges.extend(_get_stanza_edges(typedef))

    meta = _get_meta(obo_ontology)

    graph = Graph(
        id=f"http://purl.obolibrary.org/obo/{obo_ontology.ontology}.owl",
        prefix=obo_ontology.ontology,
        meta=meta,
        nodes=nodes,
        edges=edges,
        standardized=True,  # from construction :)
    )

    return graph


def _get_meta(obo_ontology: Obo) -> Meta:
    return Meta(
        version=obo_ontology.data_version,
    )


def _rewire(r: curies.Reference | Referenced) -> curies.Reference:
    return curies.Reference(prefix=r.prefix, identifier=r.identifier)


def _get_stanza_meta(stanza: Stanza) -> Meta:
    if stanza.provenance or stanza.definition:
        definition = Definition.from_parsed(
            value=stanza.definition, references=[_rewire(p) for p in stanza.provenance or []]
        )
    else:
        definition = None
    xrefs = [
        Xref.from_parsed(
            predicate=_rewire(mapping_predicate),
            value=_rewire(mapping_object),
        )
        for mapping_predicate, mapping_object in stanza.get_mappings(
            include_xrefs=True, add_context=False
        )
    ]
    synonyms = [
        Synonym.from_parsed(
            name=synonym.name,
            predicate=synonym.predicate,
            synonym_type=_rewire(synonym.type) if synonym.type else None,
            references=[_rewire(x) for x in synonym.provenance],
        )
        for synonym in stanza.synonyms
    ]

    meta = Meta(
        definition=definition,
        xrefs=xrefs,
        synonyms=synonyms,
        basicPropertyValues=None,  # TODO properties
        deprecated=stanza.is_obsolete or False,
    )
    return meta


def _get_typedef_node(term: TypeDef) -> Node:
    meta = _get_stanza_meta(term)
    return Node(
        id=term.bioregistry_link,
        lbl=term.name,
        meta=meta,
        type="PROPERTY",
        reference=_rewire(term.reference),
        standardized=True,
    )


def _get_class_node(term: Term) -> Node:
    meta = _get_stanza_meta(term)
    return Node(
        id=term.bioregistry_link,
        lbl=term.name,
        meta=meta,
        type="CLASS" if term.type == "Term" else "INDIVIDUAL",
        reference=_rewire(term.reference),
        standardized=True,
    )


def _get_stanza_edges(term: Stanza) -> Iterable[Edge]:
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
        yield Edge.from_parsed(
            _rewire(term.reference),
            _rewire(definition_source.reference),
            _rewire(provenance_reference),
        )
    # TODO also look through xrefs and seealso to get provenance xrefs?
