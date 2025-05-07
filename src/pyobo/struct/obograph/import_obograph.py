"""Import of OBO Graph JSON."""

from obographs import (
    NodeType,
    StandardizedGraph,
    StandardizedMeta,
    StandardizedNode,
    StandardizedSynonym,
)

from pyobo import Obo, Reference, StanzaType, Synonym, Term, TypeDef
from pyobo.struct import Annotation, OBOLiteral, make_ad_hoc_ontology
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
                terms[stanza.reference] = stanza
            case TypeDef():
                typedefs[stanza.reference] = stanza

    for edge in graph.edges:
        s, p, o = (Reference.from_reference(r) for r in (edge.subject, edge.predicate, edge.object))

        if s in terms:
            stanza = terms[s]
            stanza.append_relationship(p, o)
        elif s in typedefs:
            stanza = typedefs[s]
            stanza.append_relationship(p, o)

    root_terms: list[Reference] = []
    property_values = []
    auto_generated_by: str | None = None
    if graph.meta:
        for prop in graph.meta.properties or []:
            predicate = Reference.from_reference(prop.predicate)
            if predicate == has_ontology_root_term:
                if isinstance(prop.value, str):
                    raise TypeError
                else:
                    root_terms.append(Reference.from_reference(prop.value))
            elif predicate.pair == ("oboinowl", "auto_generated_by"):
                if not isinstance(prop.value, str):
                    raise TypeError
                auto_generated_by = prop.value
            # TODO specific subsetdef, imports
            else:
                property_values.append(
                    Annotation(
                        predicate=predicate,
                        # TODO obographs are limited by ability to specify datatype?
                        value=OBOLiteral.string(prop.value)
                        if isinstance(prop.value, str)
                        else Reference.from_reference(prop.value),
                    )
                )

    return make_ad_hoc_ontology(
        _ontology=prefix,
        _name=graph.name,
        terms=list(terms.values()),
        _typedefs=list(typedefs.values()),
        _root_terms=root_terms,
        _property_values=property_values,
        _data_version=graph.meta.version if graph.meta is not None else None,
        _auto_generated_by=auto_generated_by,
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
