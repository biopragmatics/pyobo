"""A DSL for functional OWL."""

from __future__ import annotations

import itertools as itt
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import ClassVar, Literal, TypeAlias

import bioregistry
from curies import Reference
from rdflib import OWL, RDF, RDFS, XSD, Graph, collection, term

__all__ = [
    "Annotation",
    "AnnotationAssertion",
    "AnnotationAxiom",
    "AnnotationPropertyDomain",
    "AnnotationPropertyRange",
    "Assertion",
    "AsymmetricObjectProperty",
    "Axiom",
    "ClassAssertion",
    "ClassAxiom",
    "ClassExpression",
    "DataAllValuesFrom",
    "DataComplementOf",
    "DataExactCardinality",
    "DataHasValue",
    "DataIntersectionOf",
    "DataMaxCardinality",
    "DataMinCardinality",
    "DataOneOf",
    "DataPropertyAssertion",
    "DataPropertyAxiom",
    "DataPropertyDomain",
    "DataPropertyExpression",
    "DataPropertyRange",
    "DataRange",
    "DataSomeValuesFrom",
    "DataUnionOf",
    "DatatypeDefinition",
    "DatatypeRestriction",
    "Declaration",
    "DeclarationType",
    "DifferentIndividuals",
    "DisjointClasses",
    "DisjointDataProperties",
    "DisjointObjectProperties",
    "DisjointUnion",
    "EquivalentClasses",
    "EquivalentDataProperties",
    "EquivalentObjectProperties",
    "FunctionalDataProperty",
    "FunctionalObjectProperty",
    "HasKey",
    "InverseFunctionalObjectProperty",
    "InverseObjectProperties",
    "IrreflexiveObjectProperty",
    "NegativeDataPropertyAssertion",
    "NegativeObjectPropertyAssertion",
    "Nodeable",
    "ObjectAllValuesFrom",
    "ObjectComplementOf",
    "ObjectExactCardinality",
    "ObjectHasSelf",
    "ObjectHasValue",
    "ObjectIntersectionOf",
    "ObjectInverseOf",
    "ObjectMaxCardinality",
    "ObjectMinCardinality",
    "ObjectOneOf",
    "ObjectPropertyAssertion",
    "ObjectPropertyAxiom",
    "ObjectPropertyChain",
    "ObjectPropertyDomain",
    "ObjectPropertyExpression",
    "ObjectPropertyRange",
    "ObjectSomeValuesFrom",
    "ObjectUnionOf",
    "Ontology",
    "ReflexiveObjectProperty",
    "SameIndividual",
    "SubAnnotationPropertyOf",
    "SubClassOf",
    "SubDataPropertyOf",
    "SubObjectPropertyExpression",
    "SubObjectPropertyOf",
    "SymmetricObjectProperty",
    "TransitiveObjectProperty",
    "c",
    "l",
    "write_ontology",
]

NNode: TypeAlias = term.URIRef | Reference
IdentifierHint = term.URIRef | Reference | str

Class: TypeAlias = NNode
Datatype: TypeAlias = NNode
ObjectProperty: TypeAlias = NNode
DataProperty: TypeAlias = NNode
AnnotationProperty: TypeAlias = NNode
NamedIndividual: TypeAlias = NNode


def c(curie: str) -> Reference:
    """Get a reference from a CURIE."""
    return Reference.from_curie(curie)


def l(value) -> term.Literal:  # noqa:E743
    """Get a literal."""
    return term.Literal(value)


def _nnode_to_funowl(node: NNode) -> str:
    if isinstance(node, Reference):
        return node.curie
    else:
        return f"<{node}>"


def _nnode_to_uriref(node: NNode) -> term.URIRef:
    if isinstance(node, term.URIRef):
        return node
    x = bioregistry.get_iri(node.prefix, node.identifier)
    if not x:
        raise ValueError
    return term.URIRef(x)


class Nodeable(ABC):
    """A model for objects that can be represented as nodes in RDF."""

    @abstractmethod
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        """Make RDF."""

    def to_funowl(self) -> str:
        """Make functional OWL."""
        tag = self.__class__.__name__
        return f"{tag}( {self._funowl_inside()} )"

    @abstractmethod
    def _funowl_inside(self) -> str:
        raise NotImplementedError


def safe_nodable(nodeable: Nodeable | IdentifierHint) -> Nodeable:
    if isinstance(nodeable, IdentifierHint):
        return SimpleNodeable(nodeable)
    return nodeable


def write_ontology(
    *,
    prefixes: dict[str, str],
    iri: str,
    version_iri: str | None = None,
    directly_imports_documents: list[str] | None = None,
    annotations: Annotations | None = None,
    axioms: list[Axiom] | None = None,
    file=None,
) -> None:
    """Write an ontology."""
    ontology = Ontology(
        prefixes=prefixes,
        iri=iri,
        version_iri=version_iri,
        directly_imports_documents=directly_imports_documents,
        annotations=annotations,
        axioms=axioms,
    )
    print(ontology.to_funowl(), file=file)


class Ontology(Nodeable):
    def __init__(
        self,
        prefixes: dict[str, str],
        iri: str,
        version_iri: str | None = None,
        directly_imports_documents: list[str] | None = None,
        annotations: Annotations | None = None,
        axioms: list[Axiom] | None = None,
    ) -> None:
        self.prefixes = prefixes
        self.iri = iri
        self.version_iri = version_iri
        self.directly_imports_documents = directly_imports_documents
        self.annotations = annotations
        self.axioms = axioms

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def to_funowl(self) -> str:
        rv = "\n".join(
            f"Prefix({prefix}:=<{uri_prefix}>)" for prefix, uri_prefix in self.prefixes.items()
        )
        rv += f"\n\nOntology(<{self.iri}>"
        if self.version_iri:
            rv += f" <{self.version_iri}>"
        rv += "\n"
        rv += "\n".join(annotation.to_funowl() for annotation in self.annotations or [])
        rv += "\n"
        rv += "\n".join(axiom.to_funowl() for axiom in self.axioms or [])
        rv += "\n)"
        return rv

    def _funowl_inside(self) -> str:
        raise RuntimeError


def _list_to_funowl(elements: Iterable[Nodeable | Reference]):
    return " ".join(
        element.to_funowl() if isinstance(element, Nodeable) else element.curie
        for element in elements
    )


class SimpleNodeable(Nodeable):
    """A simple wrapper around CURIEs and IRIs."""

    identifier: term.URIRef | Reference

    def __init__(self, identifier: IdentifierHint):
        if isinstance(identifier, str):
            self.identifier = Reference.from_curie(identifier)
        elif isinstance(identifier, Reference):
            self.identifier = identifier
        elif isinstance(identifier, term.URIRef):
            self.identifier = identifier
        else:
            raise TypeError

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _nnode_to_uriref(self.identifier)

    def to_funowl(self) -> str:
        return _nnode_to_funowl(self.identifier)

    def _funowl_inside(self) -> str:
        raise NotImplementedError


def _make_sequence(graph: Graph, members: Iterable[Nodeable]) -> term.Node:
    """Make a sequence."""
    return _make_sequence_nodes(graph, [m.to_rdflib_node(graph) for m in members])


def _make_sequence_nodes(graph: Graph, members: list[term.Node]) -> term.Node:
    """Make a sequence."""
    if not members:
        return RDF.nil
    node = term.BNode()
    collection.Collection(graph, node, members)
    return node


def _int_to_rdf(n: int) -> term.Literal:
    # "n"^^xsd:nonNegativeInteger
    return term.Literal(str(n), datatype=XSD.nonNegativeInteger)


def _literal_to_funowl(literal: term.Literal):
    if literal.datatype is None or literal.datatype == XSD.string:
        return f'"{literal.value}"'
    if literal.datatype == XSD.integer:
        return f'"{literal.toPython()}"^^xsd:integer'
    raise NotImplementedError(f"Not implemented for type: {literal.datatype}")


"""Section 5"""

DeclarationType: TypeAlias = Literal[
    "Class",
    "ObjectProperty",
    "DataProperty",
    "Datatype",
    "AnnotationProperty",
    "NamedIndividual",
]
type_to_uri: dict[DeclarationType, term.URIRef] = {
    "Class": OWL.Class,
    "ObjectProperty": OWL.ObjectProperty,
    "DataProperty": OWL.DatatypeProperty,
    "AnnotationProperty": OWL.AnnotationProperty,
    "Datatype": RDFS.Datatype,
    "NamedIndividual": OWL.NamedIndividual,
}


class Declaration(Nodeable):
    """Declarations."""

    def __init__(self, node: NNode, dtype: DeclarationType) -> None:
        self.node = node
        self.dtype = dtype

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = _nnode_to_uriref(self.node)
        graph.add((node, RDF.type, type_to_uri[self.dtype]))
        return node

    def to_funowl(self) -> str:
        return f"Declaration( {self.dtype}( {_nnode_to_funowl(self.node)} ) )"

    def _funowl_inside(self) -> str:
        raise NotImplementedError


"""
Section 6: Property Expressions
"""


class ObjectPropertyExpression(Nodeable):
    """A model representing `6.1 "Object Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_objectproperty.gif
    """

    @classmethod
    def safe(cls, ope: ObjectPropertyExpression | IdentifierHint) -> ObjectPropertyExpression:
        if isinstance(ope, IdentifierHint):
            return SimpleObjectPropertyExpression(ope)
        return ope


class SimpleObjectPropertyExpression(SimpleNodeable, ObjectPropertyExpression):
    """A simple object property expression represented by an IRI/CURIE."""


class ObjectInverseOf(ObjectPropertyExpression):
    """A property expression defined in `6.1.1 "Inverse Object Properties" <https://www.w3.org/TR/owl2-syntax/#Inverse_Object_Properties>`_.

    For example, ``ObjectPropertyAssertion( a:fatherOf a:Peter a:Stewie )`` implies
    ``ObjectPropertyAssertion( ObjectInverseOf(a:fatherOf) a:Stewie a:Peter )``.

    >>> ObjectInverseOf("a:fatherOf")

    .. warning::

        This is the only instance in the specification where the
        name of the tag is not the same as the name of the element
        in the spec, which is ``InverseObjectProperty``.
    """

    def __init__(
        self, object_property_expression: ObjectPropertyExpression | IdentifierHint
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, OWL.inverseOf, self.object_property_expression.to_rdflib_node(graph)))
        return node

    def _funowl_inside(self) -> str:
        return self.object_property_expression.to_funowl()


class DataPropertyExpression(Nodeable):  # 6.2
    """A model representing `6.2 "Data Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_dataproperty.gif
    """

    @classmethod
    def safe(cls, dpe: DataPropertyExpression | IdentifierHint) -> DataPropertyExpression:
        if isinstance(dpe, IdentifierHint):
            return SimpleDataPropertyExpression(dpe)
        return dpe


class SimpleDataPropertyExpression(SimpleNodeable, DataPropertyExpression):
    """A simple data property expression represented by an IRI/CURIE."""


"""
Section 7: Data Ranges
"""


class DataRange(Nodeable):
    """

    `7 "Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Datatypes>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_datarange.gif
    """

    @classmethod
    def safe(cls, data_range: DataRange | IdentifierHint) -> DataRange:
        if isinstance(data_range, IdentifierHint):
            return SimpleDateRange(data_range)
        return data_range


class SimpleDateRange(SimpleNodeable, DataRange):
    """A simple data range represented by an IRI/CURIE."""


class _ListDataRange(DataRange):
    property_type: ClassVar[term.URIRef]

    def __init__(self, data_ranges: Sequence[DataRange | IdentifierHint]):
        self.data_ranges = [DataRange.safe(dr) for dr in data_ranges]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def _funowl_inside(self) -> str:
        return _list_to_funowl(self.data_ranges)


class DataIntersectionOf(_ListDataRange):
    property_type: ClassVar[term.URIRef] = OWL.intersectionOf


class DataUnionOf(_ListDataRange):
    property_type: ClassVar[term.URIRef] = OWL.unionOf


class DataComplementOf(DataRange):
    def __init__(self, data_range: DataRange | IdentifierHint):
        self.data_range = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, OWL.datatypeComplementOf, self.data_range.to_rdflib_node(graph)))
        return node

    def _funowl_inside(self) -> str:
        return self.data_range.to_funowl()


class DataOneOf(DataRange):
    def __init__(self, literals: Sequence[term.Literal]):
        self.literals = literals

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, OWL.oneOf, _make_sequence_nodes(graph, self.literals)))
        return node

    def _funowl_inside(self) -> str:
        return " ".join(_literal_to_funowl(literal) for literal in self.literals)


class DatatypeRestriction(DataRange):
    def __init__(self, dtype: NNode, pairs: list[tuple[NNode, term.Literal]]) -> None:
        self.dtype = dtype
        self.pairs = pairs

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def _funowl_inside(self) -> str:
        y = " ".join(
            f"{_nnode_to_funowl(facet)} {_literal_to_funowl(value)}" for facet, value in self.pairs
        )
        return f"{_nnode_to_funowl(self.dtype)} {y}"


"""
`Section 8: Class Expressions <https://www.w3.org/TR/owl2-syntax/#Class_Expressions>`_
"""


class ClassExpression(Nodeable):
    """An abstract model representing class expressions."""

    @classmethod
    def safe(cls, class_expresion: ClassExpression | IdentifierHint) -> ClassExpression:
        if isinstance(class_expresion, IdentifierHint):
            return SimpleClassExpression(class_expresion)
        return class_expresion


class SimpleClassExpression(SimpleNodeable, ClassExpression):
    """A simple class expression represented by an IRI/CURIE."""


class _ObjectList(ClassExpression):
    """An abstract model for class expressions defined by lists.

    Defined in `8.1 Propositional Connectives and Enumeration of
    Individuals <Propositional_Connectives_and_Enumeration_of_Individuals>`_

    .. image:: https://www.w3.org/TR/owl2-syntax/C_propositional.gif
    """

    property_type: ClassVar[term.URIRef]

    def __init__(self, class_expressions: Sequence[ClassExpression | IdentifierHint]) -> None:
        """Initialize the model with a list of class expressions."""
        if len(class_expressions) < 2:
            raise ValueError("must have at least two class expressions")
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, self.property_type, _make_sequence(graph, self.class_expressions)))
        return node

    def _funowl_inside(self) -> str:
        return _list_to_funowl(self.class_expressions)


class ObjectIntersectionOf(_ObjectList):
    """A class expression defined in `8.1.1 Intersection of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Class_Expressions>`_."""

    property_type: ClassVar[term.URIRef] = OWL.intersectionOf


class ObjectUnionOf(_ObjectList):
    """A class expression defined in `8.1.2 Union of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Union_of_Class_Expressions>`_."""

    property_type: ClassVar[term.URIRef] = OWL.unionOf


class ObjectComplementOf(ClassExpression):
    """A class expression defined in `8.1.3 Complement of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Complement_of_Class_Expressions>`_."""

    def __init__(self, class_expression: ClassExpression | IdentifierHint) -> None:
        """Initialize the model with a single class expression."""
        self.class_expression = ClassExpression.safe(class_expression)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, OWL.complementOf, self.class_expression.to_rdflib_node(graph)))
        return node

    def _funowl_inside(self) -> str:
        return self.class_expression.to_funowl()


class ObjectOneOf(_ObjectList):
    """A class expression defined in `8.1.4 Enumeration of Individuals <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Individuals>`_."""

    # TODO restrict to individuals

    property_type: ClassVar[term.URIRef] = OWL.oneOf


def _owl_rdf_restriction(
    graph: Graph, prop: Nodeable, target_property: term.URIRef, target: Nodeable | term.Literal
) -> term.BNode:
    # this is shared between several class expressions
    node = term.BNode()
    graph.add((node, RDF.type, OWL.Restriction))
    graph.add((node, OWL.onProperty, prop.to_rdflib_node(graph)))
    target.to_rdflib_node(graph) if isinstance(target, Nodeable) else target
    graph.add((node, target_property, target))
    return node


class _ObjectValuesFrom(ClassExpression):
    object_expression_predicate: ClassVar[term.URIRef]

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierHint,
        class_expression: ClassExpression | IdentifierHint,
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.object_expression = ClassExpression.safe(class_expression)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _owl_rdf_restriction(
            graph,
            self.object_property_expression,
            self.object_expression_predicate,
            self.object_expression,
        )

    def _funowl_inside(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.object_expression.to_funowl()}"


class ObjectSomeValuesFrom(_ObjectValuesFrom):
    """A class expression defined in `8.2.1 Existential Quantification <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification>`_."""

    object_expression_predicate: ClassVar[term.URIRef] = OWL.someValuesFrom


class ObjectAllValuesFrom(_ObjectValuesFrom):
    """A class expression defined in `8.2.2  Universal Quantification <https://www.w3.org/TR/owl2-syntax/# Universal_Quantification>`_."""

    object_expression_predicate: ClassVar[term.URIRef] = OWL.allValuesFrom


class ObjectHasValue(ClassExpression):
    """A class expression defined in `8.2.3 Individual Value Restriction <https://www.w3.org/TR/owl2-syntax/#Individual_Value_Restriction>`_."""

    object_property_expression: ObjectPropertyExpression
    individual: Nodeable

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierHint,
        individual: Nodeable | IdentifierHint,
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.individual = safe_nodable(individual)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _owl_rdf_restriction(
            graph, self.object_property_expression, OWL.hasValue, self.individual
        )

    def _funowl_inside(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.individual.to_funowl()}"


class ObjectHasSelf(ClassExpression):
    """A class expression defined in `8.2.4 Self-Restriction <https://www.w3.org/TR/owl2-syntax/#Self-Restriction>`_."""

    def __init__(
        self, object_property_expression: ObjectPropertyExpression | IdentifierHint
    ) -> None:
        """Initialize the model with a property expression."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _owl_rdf_restriction(
            graph, self.object_property_expression, OWL.hasSelf, term.Literal(True)
        )

    def _funowl_inside(self) -> str:
        return self.object_property_expression.to_funowl()


class _Cardinality(ClassExpression):
    """A helper class for object and data cardinality constraints."""

    property_qualified: ClassVar[term.URIRef]
    property_unqualified: ClassVar[term.URIRef]
    ppp: ClassVar[term.URIRef]

    def __init__(
        self, n: int, property_expression: Nodeable, object_expression: Nodeable | None = None
    ) -> None:
        self.n = n
        self.property_expression = property_expression
        self.object_expression = object_expression

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        graph.add((node, OWL.onProperty, self.property_expression.to_rdflib_node(graph)))
        mv = _int_to_rdf(self.n)
        if self.object_expression is not None:
            graph.add((node, self.property_qualified, mv))
            graph.add((node, self.ppp, self.object_expression.to_rdflib_node(graph)))
        else:
            graph.add((node, self.property_unqualified, mv))
        return node

    def _funowl_inside(self) -> str:
        inside = f"{self.n} {self.property_expression.to_funowl()}"
        if self.object_expression is not None:
            inside += f" {self.object_expression.to_funowl()}"
        return inside


class _ObjectCardinality(_Cardinality):
    """A grouping class for object cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    ppp: ClassVar[term.URIRef] = OWL.onClass

    def __init__(
        self,
        n: int,
        object_property_expression: ObjectPropertyExpression | IdentifierHint,
        class_expression: ClassExpression | IdentifierHint | None = None,
    ) -> None:
        super().__init__(
            n=n,
            property_expression=ObjectPropertyExpression.safe(object_property_expression),
            object_expression=ClassExpression.safe(class_expression)
            if class_expression is not None
            else None,
        )


class ObjectMinCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.1 Minimum Cardinality <https://www.w3.org/TR/owl2-syntax/#Minimum_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.maxQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.maxCardinality


class ObjectMaxCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.2 Maximum Cardinality <https://www.w3.org/TR/owl2-syntax/#Maximum_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.minQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.minCardinality


class ObjectExactCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.2 Exact Cardinality <https://www.w3.org/TR/owl2-syntax/#Exact_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.qualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.cardinality


class _DataValuesFrom(ClassExpression):
    """A class expression defined in https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2."""

    property_type: ClassVar[term.URIRef]

    def __init__(
        self,
        data_property_expressions: list[DataPropertyExpression | IdentifierHint],
        data_range: DataRange | IdentifierHint,
    ) -> None:
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        self.data_range_expression = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        if len(self.data_property_expressions) >= 2:
            p_o = OWL.onProperties, _make_sequence(graph, self.data_property_expressions)
        else:
            p_o = OWL.onProperty, self.data_property_expressions[0].to_rdflib_node(graph)
        graph.add((node, self.property_type, self.data_range_expression.to_rdflib_node(graph)))
        graph.add((node, *p_o))
        return node

    def _funowl_inside(self) -> str:
        return _list_to_funowl((*self.data_property_expressions, self.data_range_expression))


class DataSomeValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.1 Existential Qualifications <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2>`_."""

    property_type: ClassVar[term.URIRef] = OWL.someValuesFrom


class DataAllValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.2 Universal Qualifications <https://www.w3.org/TR/owl2-syntax/#Universal_Quantification_2>`_."""

    property_type: ClassVar[term.URIRef] = OWL.allValuesFrom


class DataHasValue(_DataValuesFrom):
    """A class expression defined in `8.4.3 Literal Value Restriction <https://www.w3.org/TR/owl2-syntax/#Literal_Value_Restriction>`_."""

    property_type: ClassVar[term.URIRef] = OWL.hasValue

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierHint,
        literal: term.Literal,
    ) -> None:
        super().__init__(
            data_property_expressions=[DataPropertyExpression.safe(data_property_expression)],
            data_range=literal,
        )

    def _funowl_inside(self) -> str:
        first = _list_to_funowl(self.data_property_expressions)
        return f"{first} {_literal_to_funowl(self.data_range_expression)}"


class _DataCardinality(_Cardinality):
    """A grouping class for data cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    ppp: ClassVar[term.URIRef] = OWL.onDataRange

    def __init__(
        self,
        n: int,
        data_property_expression: DataPropertyExpression | IdentifierHint,
        data_range: DataRange | IdentifierHint | None = None,
    ) -> None:
        super().__init__(
            n,
            DataPropertyExpression.safe(data_property_expression),
            DataRange.safe(data_range) if data_range is not None else None,
        )


class DataMinCardinality(_DataCardinality):
    """A class expression defined in `8.5.1 Minimum Cardinality <https://www.w3.org/TR/owl2-syntax/#Minimum_Cardinality_2>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.minQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.minCardinality


class DataMaxCardinality(_DataCardinality):
    """A class expression defined in `8.5.2 Maximum Cardinality <https://www.w3.org/TR/owl2-syntax/#Maximum_Cardinality_2>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.maxQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.maxCardinality


class DataExactCardinality(_DataCardinality):
    """A class expression defined in `8.5.3 Exact Cardinality <https://www.w3.org/TR/owl2-syntax/#Exact_Cardinality_2>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.qualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.cardinality


"""
`Section 9: Axioms <https://www.w3.org/TR/owl2-syntax/#Axioms>`_
"""


class Axiom(Nodeable, ABC):
    def __init__(self, annotations: list[Annotation] | None = None):
        self.annotations = annotations

    def _funowl_inside(self) -> str:
        if self.annotations:
            return _list_to_funowl(self.annotations) + " " + self._funowl_inside_2()
        return self._funowl_inside_2()

    @abstractmethod
    def _funowl_inside_2(self) -> str:
        raise NotImplementedError


class ClassAxiom(Axiom):
    pass


def _add_triple(
    graph: Graph, s: term.Node, p: term.Node, o: term.Node, annotations: Annotations | None = None
) -> term.BNode | None:
    graph.add((s, p, o))
    return _add_triple_annotations(graph, s, p, o, annotations)


def _add_triple_annotations(
    graph: Graph,
    s: term.Node,
    p: term.Node,
    o: term.Node,
    *,
    annotations: Annotations | None = None,
    type=None,
) -> term.BNode | None:
    if not annotations:
        return None
    node = term.BNode()
    if type:
        graph.add((node, RDF.type, type))
    graph.add((node, OWL.annotatedSource, s))
    graph.add((node, OWL.annotatedProperty, p))
    graph.add((node, OWL.annotatedTarget, o))
    for annotation in annotations:
        annotation._add_to_triple(graph, node)
    return node


class SubClassOf(ClassAxiom):  # 9.1.1
    def __init__(
        self,
        child: ClassExpression | IdentifierHint,
        parent: ClassExpression | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.child = ClassExpression.safe(child)
        self.parent = ClassExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.child.to_rdflib_node(graph)
        o = self.parent.to_rdflib_node(graph)
        return _add_triple(graph, s, RDFS.subClassOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class EquivalentClasses(ClassAxiom):  # 9.1.2
    def __init__(
        self,
        class_expressions: Sequence[ClassExpression | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if len(class_expressions) < 2:
            raise ValueError
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> None:
        nodes = [ce.to_rdflib_node(graph) for ce in self.class_expressions]
        for s, o in itt.combinations(nodes, 2):
            _add_triple(graph, s, OWL.equivalentClass, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.class_expressions)


class DisjointClasses(ClassAxiom):  # 9.1.3
    def __init__(
        self,
        class_expressions: Sequence[ClassExpression],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if len(class_expressions) < 2:
            raise ValueError
        self.class_expressions = class_expressions
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        nodes = [ce.to_rdflib_node(graph) for ce in self.class_expressions]
        if len(nodes) == 2:
            return _add_triple(graph, nodes[0], OWL.disjointWith, nodes[1], self.annotations)
        else:
            node = term.BNode()
            graph.add((node, RDF.type, OWL.AllDisjointClasses))
            _add_triple(
                graph, node, OWL.members, _make_sequence_nodes(graph, nodes), self.annotations
            )
            return node

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.class_expressions)


class DisjointUnion(ClassAxiom):  # 9.1.4
    def __init__(
        self,
        clazz: Nodeable | IdentifierHint,
        class_expressions: Sequence[ClassExpression | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        # TODO better typing for clazz
        self.clazz = safe_nodable(clazz)
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.clazz.to_rdflib_node(graph),
            OWL.disjointUnionOf,
            _make_sequence(graph, self.class_expressions),
            self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl((self.clazz, *self.class_expressions))


"""Section 9.2: Object Property Axioms"""


class ObjectPropertyAxiom(Axiom):
    pass


class ObjectPropertyChain(Nodeable):
    def __init__(
        self, object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierHint]
    ):
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def _funowl_inside(self) -> str:
        return _list_to_funowl(self.object_property_expressions)


SubObjectPropertyExpression: TypeAlias = ObjectPropertyExpression | ObjectPropertyChain


class SubObjectPropertyOf(ObjectPropertyAxiom):  # 9.2.1
    child: SubObjectPropertyExpression
    parent: ObjectPropertyExpression

    def __init__(
        self,
        child: SubObjectPropertyExpression | IdentifierHint,
        parent: ObjectPropertyExpression | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if isinstance(child, ObjectPropertyChain):
            self.child = child
        else:
            self.child = ObjectPropertyExpression.safe(child)
        self.parent = ObjectPropertyExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.child.to_rdflib_node(graph)
        o = self.parent.to_rdflib_node(graph)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class _ObjectPropertyList(ObjectPropertyAxiom):
    object_property_expressions: Sequence[ObjectPropertyExpression]

    def __init__(
        self,
        object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if len(object_property_expressions) < 2:
            raise ValueError
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.object_property_expressions)


def _equivalent_xxx(
    graph: Graph, expressions: list[Nodeable], *, annotations: Annotations | None = None
):
    nodes = [expression.to_rdflib_node(graph) for expression in expressions]
    for s, o in itt.combinations(nodes, 2):
        _add_triple(graph, s, OWL.equivalentProperty, o, annotations)


class EquivalentObjectProperties(_ObjectPropertyList):  # 9.2.2
    def to_rdflib_node(self, graph: Graph) -> None:
        return _equivalent_xxx(
            graph, self.object_property_expressions, annotations=self.annotations
        )


def _disjoint_xxx(
    graph: Graph, expressions: Iterable[Nodeable], *, annotations: Annotations | None = None
) -> term.Node:
    nodes = [expression.to_rdflib_node(graph) for expression in expressions]
    if len(nodes) == 2:
        return _add_triple(graph, nodes[0], OWL.propertyDisjointWith, nodes[1], annotations)
    else:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.AllDisjointProperties))
        _add_triple(graph, node, OWL.members, _make_sequence_nodes(graph, nodes), annotations)
        return node


class DisjointObjectProperties(_ObjectPropertyList):  # 9.2.3
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _disjoint_xxx(graph, self.object_property_expressions, annotations=self.annotations)


class InverseObjectProperties(ObjectPropertyAxiom):  # 9.2.4
    def __init__(
        self,
        left: ObjectPropertyExpression,
        right: ObjectPropertyExpression,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.left = left
        self.right = right
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.left.to_rdflib_node(graph)
        o = self.right.to_rdflib_node(graph)
        return _add_triple(graph, s, OWL.inverseOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.left.to_funowl()} {self.right.to_funowl()}"


class _BinaryObjectPropertyAxiom(ObjectPropertyAxiom):  # 9.2.4
    property_type: ClassVar[term.Node]

    def __init__(
        self,
        left: ObjectPropertyExpression,
        right: ClassExpression,
        *,
        annotations: Annotations | None = None,
        property: term.Node,
    ) -> None:
        self.left = left
        self.right = right
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.left.to_rdflib_node(graph)
        o = self.right.to_rdflib_node(graph)
        return _add_triple(graph, s, self.property_type, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.left.to_funowl()} {self.right.to_funowl()}"


class ObjectPropertyDomain(_BinaryObjectPropertyAxiom):  # 9.2.5
    property_type: ClassVar[term.Node] = RDFS.domain


class ObjectPropertyRange(_BinaryObjectPropertyAxiom):  # 9.2.6
    property_type: ClassVar[term.Node] = RDFS.range


class _UnaryObjectProperty(ObjectPropertyAxiom):  # 9.2.7
    property_type: ClassVar[term.Node]

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression,
        *,
        annotations: Annotations | None = None,
        type: term.Node,
    ) -> None:
        self.object_property_expression = object_property_expression
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _add_triple(
            graph,
            self.object_property_expression.to_rdflib_node(graph),
            RDF.type,
            self.property_type,
            self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return self.object_property_expression.to_funowl()


class FunctionalObjectProperty(_UnaryObjectProperty):  # 9.2.7
    property_type: ClassVar[term.Node] = OWL.FunctionalProperty


class InverseFunctionalObjectProperty(_UnaryObjectProperty):  # 9.2.8
    property_type: ClassVar[term.Node] = OWL.InverseFunctionalProperty


class ReflexiveObjectProperty(_UnaryObjectProperty):  # 9.2.9
    property_type: ClassVar[term.Node] = OWL.ReflexiveProperty


class IrreflexiveObjectProperty(_UnaryObjectProperty):  # 9.2.10
    property_type: ClassVar[term.Node] = OWL.IrreflexiveProperty


class SymmetricObjectProperty(_UnaryObjectProperty):  # 9.2.11
    property_type: ClassVar[term.Node] = OWL.SymmetricProperty


class AsymmetricObjectProperty(_UnaryObjectProperty):  # 9.2.12
    property_type: ClassVar[term.Node] = OWL.AsymmetricProperty


class TransitiveObjectProperty(_UnaryObjectProperty):  # 9.2.13
    property_type: ClassVar[term.Node] = OWL.TransitiveProperty


"""9.3: Data Property Axioms"""


class DataPropertyAxiom(Axiom):
    pass


class SubDataPropertyOf(DataPropertyAxiom):  # 9.3.1
    def __init__(
        self,
        child: DataPropertyExpression | IdentifierHint,
        parent: DataPropertyExpression | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.child = DataPropertyExpression.safe(child)
        self.parent = DataPropertyExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.child.to_rdflib_node(graph)
        o = self.parent.to_rdflib_node(graph)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class _DataPropertyList(DataPropertyAxiom):
    def __init__(
        self,
        data_property_expressions: Sequence[DataPropertyExpression | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if len(data_property_expressions) < 2:
            raise ValueError
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.data_property_expressions)


class EquivalentDataProperties(_DataPropertyList):  # 9.3.2
    def to_rdflib_node(self, graph: Graph) -> None:
        return _equivalent_xxx(graph, self.data_property_expressions, annotations=self.annotations)


class DisjointDataProperties(_DataPropertyList):  # 9.3.2
    def to_rdflib_node(self, graph: Graph) -> None:
        return _disjoint_xxx(graph, self.data_property_expressions, annotations=self.annotations)


class _BinaryDataPropertyAxiom(DataPropertyAxiom):  # 9.2.4
    property_type: ClassVar[term.Node]

    def __init__(
        self,
        left: DataPropertyExpression | IdentifierHint,
        right: ClassExpression | IdentifierHint,
        *,
        annotations: Annotations | None = None,
        property: term.Node,
    ) -> None:
        self.left = DataPropertyExpression.safe(left)
        self.right = ClassExpression.safe(right)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.left.to_rdflib_node(graph)
        o = self.right.to_rdflib_node(graph)
        return _add_triple(graph, s, self.property_type, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.left.to_funowl()} {self.right.to_funowl()}"


class DataPropertyDomain(_BinaryDataPropertyAxiom):  # 9.3.4
    property_type: ClassVar[term.Node] = RDFS.domain


class DataPropertyRange(_BinaryDataPropertyAxiom):  # 9.3.5
    property_type: ClassVar[term.Node] = RDFS.range


class FunctionalDataProperty(DataPropertyAxiom):  # 9.3.6
    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ):
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.data_property_expression.to_rdflib_node(graph),
            RDF.type,
            OWL.FunctionalProperty,
            self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return self.data_property_expression.to_funowl()


"""Section 9.4: Datatype Definitions"""


class DatatypeDefinition(Axiom):
    def __init__(
        self, datatype: NNode, data_range: DataRange, *, annotations: Annotations | None = None
    ) -> None:
        self.datatype = datatype
        self.data_range = data_range
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            _nnode_to_uriref(self.datatype),
            OWL.equivalentClass,
            self.data_range.to_rdflib_node(graph),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return f"{_nnode_to_funowl(self.datatype)} {self.data_range.to_funowl()}"


"""Section 9.5: Keys"""


class HasKey(Axiom):
    object_property_expressions: list[ObjectPropertyExpression]
    data_property_expressions: list[DataPropertyExpression]

    def __init__(
        self,
        class_expression: ClassExpression | IdentifierHint,
        object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierHint],
        data_property_expressions: Sequence[DataPropertyExpression | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.class_expression = ClassExpression.safe(class_expression)
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        ss: list[ObjectPropertyExpression | DataPropertyExpression] = []
        ss.extend(self.object_property_expressions)
        ss.extend(self.data_property_expressions)

        return _add_triple(
            graph,
            self.class_expression.to_rdflib_node(graph),
            OWL.hasKey,
            _make_sequence(graph, ss),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        aa = f"{self.class_expression.to_funowl()}"
        if self.object_property_expressions:
            aa += f" ( {_list_to_funowl(self.object_property_expressions)} )"
        else:
            aa += " ()"
        if self.data_property_expressions:
            aa += f" ( {_list_to_funowl(self.data_property_expressions)} )"
        else:
            aa += " ()"
        return aa


"""Section 9.6: Assertions"""


class Assertion(Axiom):
    pass


class _IndividualListAssertion(Assertion):
    def __init__(
        self,
        individuals: Sequence[Nodeable | IdentifierHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.individuals = [safe_nodable(i) for i in individuals]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.individuals)


class SameIndividual(_IndividualListAssertion):  # 9.6.1
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        for s, o in itt.combinations(self.individuals, 2):
            _add_triple(graph, s, OWL.sameAs, o, annotations=self.annotations)


class DifferentIndividuals(_IndividualListAssertion):  # 9.6.2
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        nodes = self.individuals
        if len(nodes) == 2:
            return _add_triple(
                graph, nodes[0], OWL.differentFrom, nodes[1], annotations=self.annotations
            )
        else:
            node = term.BNode()
            graph.add((node, RDF.type, OWL.AllDifferent))
            graph.add((node, OWL.distinctMembers, _make_sequence_nodes(graph, nodes)))
            # FIXME add annotations
            return node


class ClassAssertion(Assertion):  # 9.6.3
    def __init__(
        self,
        class_expression: ClassExpression | IdentifierHint,
        individual: Nodeable | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.class_expression = ClassExpression.safe(class_expression)
        self.individual = safe_nodable(individual)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.class_expression.to_rdflib_node(graph),
            RDF.type,
            self.individual.to_rdflib_node(graph),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return f"{self.class_expression.to_funowl()} {self.individual.to_funowl()}"


class _ObjectPropertyAssertion(Assertion):
    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierHint,
        source_individual: Nodeable | IdentifierHint,
        target_individual: Nodeable | IdentifierHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.source_individual = safe_nodable(source_individual)
        self.target_individual = safe_nodable(target_individual)
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.source_individual.to_funowl()} {self.target_individual.to_funowl()}"


class ObjectPropertyAssertion(_ObjectPropertyAssertion):  # 9.6.4
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        s = self.source_individual.to_rdflib_node(graph)
        o = self.target_individual.to_rdflib_node(graph)
        if isinstance(self.object_property_expression, ObjectInverseOf):
            # flip them around
            s, o = o, s
            # unpack the inverse property
            p = self.object_property_expression.object_property_expression.to_rdflib_node(graph)
        else:
            p = self.object_property_expression.to_rdflib_node(graph)

        return _add_triple(graph, s, p, o, annotations=self.annotations)


class NegativeObjectPropertyAssertion(_ObjectPropertyAssertion):  # 9.6.5
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        s = self.source_individual.to_rdflib_node(graph)
        o = self.target_individual.to_rdflib_node(graph)
        if isinstance(self.object_property_expression, ObjectInverseOf):
            # flip them around
            s, o = o, s
            # unpack the inverse property
            p = self.object_property_expression.object_property_expression.to_rdflib_node(graph)
        else:
            p = self.object_property_expression.to_rdflib_node(graph)
        return _add_triple_annotations(
            graph, s, p, o, annotations=self.annotations, type=OWL.NegativePropertyAssertion
        )


class _DataPropertyAssertion(Assertion):
    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierHint,
        source: Nodeable | IdentifierHint,
        target: term.Literal,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.source = safe_nodable(source)
        self.target = target
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.data_property_expression.to_funowl()} {self.source.to_funowl()} {_literal_to_funowl(self.target)}"


class DataPropertyAssertion(_DataPropertyAssertion):  # 9.6.6
    """DataPropertyAssertion( a:hasAge a:Meg "17"^^xsd:integer )."""

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.source.to_rdflib_node(graph),
            self.data_property_expression.to_rdflib_node(graph),
            self.target,
            annotations=self.annotations,
        )


class NegativeDataPropertyAssertion(_DataPropertyAssertion):  # 9.6.7
    """NegativeDataPropertyAssertion( a:hasAge a:Meg "5"^^xsd:integer )."""

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple_annotations(
            graph,
            self.source.to_rdflib_node(graph),
            self.data_property_expression.to_rdflib_node(graph),
            self.target,
            annotations=self.annotations,
            type=OWL.NegativePropertyAssertion,
        )


"""Section 10: Annotations"""

AnnotationValue: TypeAlias = NNode | term.Literal  # TODO add anonmyous individual
AnnotationSubject: TypeAlias = NNode  # TODO anonymous


def _annotation_value_to_funowl(value: AnnotationValue) -> str:
    if isinstance(value, term.Literal):
        return _literal_to_funowl(value)
    else:
        return _nnode_to_funowl(value)


def _annotation_value_to_rdf(value: AnnotationValue):
    if isinstance(value, term.Literal):
        return value
    else:
        return _nnode_to_uriref(value)


class Annotation(Nodeable):  # 10.1
    """An element defined in `10.1 "Annotations of Ontologies, Axioms, and other Annotations" <https://www.w3.org/TR/owl2-syntax/#Annotations_of_Ontologies.2C_Axioms.2C_and_other_Annotations>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/Annotations.gif

    Annotations can be used to add additional context, like curation provenance, to
    assertions

    >>> ObjectPropertyAssertion(
    ...     c(""),
    ...     c(""),
    ...     c(""),
    ...     annotations=[Annotation(c("dcterms:contributor"), c("orcid:0000-0003-4423-4370"))],
    ... )

    Annotations can even be used on themselves, adding arbitrary levels of detail.
    In the following example, we annotate the affiliation of the contributor.

    >>> ObjectPropertyAssertion(
    ...     c(""),
    ...     c(""),
    ...     c(""),
    ...     annotations=[
    ...         Annotation(
    ...             c("dcterms:contributor"),
    ...             c("orcid:0000-0003-4423-4370"),
    ...             annotations=[
    ...                 Annotation(c(""), c("")),
    ...             ],
    ...         )
    ...     ],
    ... )

    """

    def __init__(
        self,
        annotation_property: AnnotationProperty,
        value: AnnotationValue,
        *,
        annotations: list[Annotation] | None = None,
    ):
        self.annotation_property = annotation_property
        self.value = value
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise RuntimeError

    def _add_to_triple(self, graph: Graph, node: term.BNode) -> None:
        graph.add(
            (node, _nnode_to_uriref(self.annotation_property), _annotation_value_to_rdf(self.value))
        )

    def _funowl_inside(self) -> str:
        end = f"{_nnode_to_funowl(self.annotation_property)} {_annotation_value_to_funowl(self.value)}"
        if self.annotations:
            return _list_to_funowl(self.annotations) + " " + end
        return end


Annotations: TypeAlias = list[Annotation]


class AnnotationAxiom(Axiom):  # 10.2
    """A grouping class for annotation axioms defined in `10.2 "Axiom Annotations" <https://www.w3.org/TR/owl2-syntax/#Annotation_Axioms>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/A_annotation.gif
    """


class AnnotationAssertion(AnnotationAxiom):  # 10.2.1
    """An annotation axiom defined in `10.2.1 Annotation Assertion <https://www.w3.org/TR/owl2-syntax/#Annotation_Assertion>`_."""

    def __init__(
        self,
        annotation_property: AnnotationProperty,
        subject: AnnotationSubject,
        value: AnnotationValue,
        *,
        annotations: list[Annotation] | None = None,
    ) -> None:
        self.annotation_property = annotation_property
        self.subject = subject
        self.value = value
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            _nnode_to_uriref(self.subject),
            _nnode_to_uriref(self.annotation_property),
            _annotation_value_to_rdf(self.value),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return " ".join(
            (
                _nnode_to_funowl(self.annotation_property),
                _nnode_to_funowl(self.subject),
                _annotation_value_to_funowl(self.value),
            )
        )


class SubAnnotationPropertyOf(AnnotationAxiom):  # 10.2.2
    """An annotation axiom defined in `10.2.2 Annotation Subproperties <https://www.w3.org/TR/owl2-syntax/#Annotation_Subproperties>`_."""

    def __init__(
        self,
        child: AnnotationProperty,
        parent: AnnotationProperty,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.child = child
        self.parent = parent
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = _nnode_to_uriref(self.child)
        o = _nnode_to_uriref(self.parent)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{_nnode_to_funowl(self.child)} {_nnode_to_funowl(self.parent)}"


class AnnotationPropertyTypingAxiom(AnnotationAxiom):
    """A helper class that defines shared functionality between annotation property domains and ranges."""

    property_type: ClassVar[term.URIRef]

    def __init__(
        self,
        annotation_property: AnnotationProperty,
        value: NNode,
        *,
        annotations: Annotations | None = None,
        property: term.Node,
    ) -> None:
        self.annotation_property = annotation_property
        self.value = value
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = _nnode_to_uriref(self.annotation_property)
        o = _nnode_to_uriref(self.value)
        return _add_triple(graph, s, self.property_type, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{_nnode_to_funowl(self.annotation_property)} {_nnode_to_funowl(self.value)}"


class AnnotationPropertyDomain(AnnotationPropertyTypingAxiom):  # 10.2.3
    """An annotation axiom defined in `10.2.3 Annotation Property Domain <https://www.w3.org/TR/owl2-syntax/#Annotation_Property_Domain>`_."""

    property_type: ClassVar[term.URIRef] = RDFS.domain


class AnnotationPropertyRange(AnnotationPropertyTypingAxiom):  # 10.2.4
    """An annotation axiom defined in `10.2.4 Annotation Property Range <https://www.w3.org/TR/owl2-syntax/#Annotation_Property_Range>`_.

    For example, the range of all ``rdfs:label`` should be a string.
    This can be represented as with the functional OWL
    ``AnnotationPropertyRange( rdfs:label xsd:string )``, or in
    Python like the following:

    Using :mod:`rdflib` namespaces:

    >>> from rdflib import RDFS, XSD
    >>> AnnotationPropertyRange(RDFS.label, XSD.string)

    Using :class:`curies.Reference`:

    >>> AnnotationPropertyRange(c("rdfs:label"), c("xsd:string"))
    """

    property_type: ClassVar[term.URIRef] = RDFS.range
