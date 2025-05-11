"""Exports to OBO Graph JSON."""

from curies import Converter
from curies.vocabulary import DEFAULT_SYNONYM_SCOPE_OIO, synonym_scope_to_oio
from obographs import Graph, GraphDocument, Meta, Node, Property, Synonym, Xref
from obographs.model import Definition, Edge

from pyobo.struct import Obo, OBOLiteral, Term


def to_obograph(obo: Obo, converter: Converter) -> GraphDocument:
    """Convert an ontology to an OBO Graph JSON document."""
    return GraphDocument(graphs=[_to_graph(obo, converter)])


def _to_graph(obo: Obo, converter: Converter) -> Graph:
    return Graph(
        id=f"http://purl.obolibrary.org/obo/{obo.ontology}.owl",
        meta=_get_meta(obo, converter),
        nodes=_get_nodes(obo, converter),
        edges=_get_edges(obo, converter),
        # TODO rest
    )


def _get_meta(obo: Obo, converter: Converter) -> Meta:
    properties = []
    for root_term in obo.root_terms or []:
        properties.append(
            Property(
                pred="http://purl.obolibrary.org/obo/IAO_0000700",
                val=converter.expand_reference(root_term.pair, strict=True),
            )
        )

    if obo.auto_generated_by:
        properties.append(
            Property(
                pred="http://www.geneontology.org/formats/oboInOwl#auto-generated-by",
                val=obo.auto_generated_by,
            )
        )

    if obo.name:
        properties.append(
            Property(
                pred="http://purl.org/dc/terms/title",
                val=obo.name,
            )
        )

    for p in obo.property_values or []:
        properties.append(
            Property(
                pred=converter.expand_reference(p.predicate.pair, strict=True),
                val=p.value.value
                if isinstance(p.value, OBOLiteral)
                else converter.expand_reference(p.value.pair, strict=True),
            )
        )

    if obo.data_version:
        version_iri = (
            f"http://purl.obolibrary.org/obo/{obo.ontology}/{obo.data_version}/{obo.ontology}.owl"
        )
    else:
        version_iri = None

    return Meta(
        basicPropertyValues=properties,
        version=version_iri,
    )


def _get_nodes(obo: Obo, converter: Converter) -> list[Node]:
    rv = []
    for term in obo:
        rv.append(_get_class_node(term, converter))
    return rv


def _get_class_node(term: Term, converter: Converter) -> Node:
    if term.definition:
        definition = Definition.from_parsed(
            value=term.definition,
            references=[converter.expand_reference(p.pair, strict=True) for p in term.provenance],
        )
    else:
        definition = None
    xrefs = [Xref(val=converter.expand_reference(xref.pair, strict=True)) for xref in term.xrefs]
    synonyms = [
        Synonym(
            val=synonym.name,
            pred=synonym_scope_to_oio[synonym.specificity]
            if synonym.specificity is not None
            else DEFAULT_SYNONYM_SCOPE_OIO,
            synonymType=converter.expand_reference(synonym.type.pair, strict=True)
            if synonym.type
            else None,
            xrefs=[converter.expand_reference(p.pair) for p in synonym.provenance],
            meta=None,
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
        id=converter.expand_reference(term.reference.pair, strict=True),
        lbl=term.name,
        meta=meta,
        type="CLASS" if term.type == "Term" else "INDIVIDUAL",
    )


def _get_edges(obo: Obo, converter: Converter) -> list[Edge]:
    return []
