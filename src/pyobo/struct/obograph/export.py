"""Exports to OBO Graph JSON."""

from curies import Converter
from obographs import Edge, Graph, GraphDocument, Meta, Node, Property

from pyobo.struct import Obo


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
                val=converter.expand_reference(root_term, strict=True),
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
                val=p.value
                if isinstance(p.value, str)
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
    return []


def _get_edges(obo: Obo, converter: Converter) -> list[Edge]:
    return []
