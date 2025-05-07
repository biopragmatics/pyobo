"""Import of OBO Graph JSON."""

from obographs import (
    NodeType,
    StandardizedGraph,
    StandardizedMeta,
    StandardizedNode,
    StandardizedSynonym,
)

from pyobo import Obo, Reference, StanzaType, Synonym, Term, TypeDef
from pyobo.struct import make_ad_hoc_ontology, Annotation, OBOLiteral
from pyobo.struct.typedef import has_ontology_root_term

__all__ = [
    "from_node",
    "from_standardized_graph",
]


def from_standardized_graph(prefix: str, graph: StandardizedGraph) -> Obo:
    """Generate an OBO data structure from OBO Graph JSON."""
    terms: dict[Reference, Term] = {}
    typedefs: dict[Reference, TypeDef] = {}
    for node in graph.nodes:
        stanza = from_node(node)
        match stanza:
            case Term():
                terms[node.reference] = stanza
            case TypeDef():
                typedefs[node.reference] = stanza

    for edge in graph.edges:
        if edge.subject in terms:
            stanza = terms[edge.subject]
            stanza.append_relationship(edge.predicate, edge.object)
        elif edge.subject in typedefs:
            stanza = terms[edge.subject]
            stanza.append_relationship(edge.predicate, edge.object)

    root_terms = []
    property_values = []
    if graph.meta:
        for property in graph.meta.properties or []:
            if property.predicate == has_ontology_root_term:
                if isinstance(property.value, str):
                    raise TypeError
                root_terms.append(property.value)
            # TODO specific for auto_generated_by, subsetdef, imports
            else:
                property_values.append(Annotation(
                    predicate=predicate,
                    # TODO obographs are limited by ability to specify datatype?
                    value=value if isinstance(value, Reference) else OBOLiteral.string(value)
                ))

    return make_ad_hoc_ontology(
        _ontology=prefix,
        _name=graph.name,
        terms=terms.values(),
        _typedefs=typedefs.values(),
        _root_terms=root_terms,
        _property_values=property_values,
        _data_version=graph.meta and graph.meta.version,
    )


#: A mapping between OBO Graph JSON node types and OBO stanza types
MAPPING: dict[NodeType, StanzaType] = {
    "CLASS": "Term",
    "INDIVIDUAL": "Instance",
    "PROPERTY": "TypeDef",
}


def from_node(node: StandardizedNode) -> Term | TypeDef:
    """Generate a term from a node."""
    if node.type == "PROPERTY":
        return _from_property(node)
    return _from_term(node)


def _from_term(node: StandardizedNode) -> Term:
    term = Term(
        reference=_get_ref(node),
        type=MAPPING[node.type] if node.type else "Term",
    )
    if node.meta is not None:
        _process_term_meta(node.meta, term)
    return term


def _from_property(node: StandardizedNode) -> TypeDef:
    typedef = TypeDef(
        reference=_get_ref(node),
    )
    if node.meta is not None:
        _process_typedef_meta(node.meta, typedef)
    return typedef


def _get_ref(node: StandardizedNode) -> Reference:
    return Reference(
        prefix=node.reference.prefix,
        identifier=node.reference.identifier,
        name=node.label,
    )


def _process_term_meta(meta: StandardizedMeta, term: Term) -> None:
    """Process the ``meta`` object associated with a term node."""
    if meta.definition:
        term.definition = meta.definition.value
        # TODO handle xrefs

    for synonym in meta.synonyms or []:
        if s := _from_synonym(synonym):
            term.append_synonym(s)

    for xref in meta.xrefs or []:
        term.append_xref(xref.reference)

    for comment in meta.comments or []:
        term.append_comment(comment)

    if meta.deprecated:
        term.is_obsolete = True

    for _prop in meta.properties or []:
        raise NotImplementedError


def _from_synonym(syn: StandardizedSynonym) -> Synonym | None:
    raise NotImplementedError


def _process_typedef_meta(meta: StandardizedMeta, typedef: TypeDef) -> None:
    """Process the ``meta`` object associated with a property node."""
    # TODO everything else is in here
