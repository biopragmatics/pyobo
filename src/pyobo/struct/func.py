"""A DSL for functional OWL."""

from __future__ import annotations

import datetime
import itertools as itt
import typing
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import ClassVar, TypeAlias, TypeVar

import bioregistry
from curies import Reference
from rdflib import OWL, RDF, RDFS, XSD, Graph, collection, term

from .func_utils import FunctionalOWLSerializable, RDFNodeSerializable

__all__ = [
    "Annotation",
    "AnnotationAssertion",
    "AnnotationAxiom",
    "AnnotationPropertyDomain",
    "AnnotationPropertyRange",
    "Assertion",
    "AsymmetricObjectProperty",
    "Axiom",
    "Box",
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


def c(curie: str) -> Reference:
    """Get a reference from a CURIE."""
    return Reference.from_curie(curie)


def l(value) -> term.Literal:  # noqa:E743
    """Get a literal."""
    return term.Literal(value)


X = TypeVar("X")
XorList: TypeAlias = X | list[X]

#: These are the literals that can be automatically converted to and from RDFLib
SupportedLiterals: TypeAlias = int | float | bool | str | datetime.date | datetime.datetime

NNode: TypeAlias = term.URIRef | Reference
IdentifierHint = term.URIRef | Reference | str


class Box(FunctionalOWLSerializable, RDFNodeSerializable):
    """A model for objects that can be represented as nodes in RDF and Functional OWL."""


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


class Ontology(Box):
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

    def to_funowl_args(self) -> str:
        raise RuntimeError


def _list_to_funowl(elements: Iterable[Box | Reference]):
    return " ".join(
        element.to_funowl() if isinstance(element, Box) else element.curie for element in elements
    )


class IdentifierBox(Box):
    """A simple wrapper around CURIEs and IRIs."""

    identifier: term.URIRef | Reference

    def __init__(self, identifier: IdentifierBoxOrHint):
        if isinstance(identifier, IdentifierBox):
            self.identifier = identifier.identifier
        # make sure to check for URIRef first,
        # since it's also a subclass of str
        elif isinstance(identifier, term.URIRef):
            self.identifier = identifier
        elif isinstance(identifier, str):
            self.identifier = Reference.from_curie(identifier)
        elif isinstance(identifier, Reference):
            self.identifier = identifier
        else:
            raise TypeError

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        if isinstance(self.identifier, term.URIRef):
            return self.identifier
        x = bioregistry.get_iri(self.identifier.prefix, self.identifier.identifier)
        if not x:
            raise ValueError
        return term.URIRef(x)

    def to_funowl(self) -> str:
        if isinstance(self.identifier, Reference):
            return self.identifier.curie
        elif isinstance(self.identifier, term.URIRef):
            return f"<{self.identifier}>"
        else:
            raise TypeError

    def to_funowl_args(self) -> str:
        raise NotImplementedError


class LiteralBox(Box):
    """A simple wrapper around a literal."""

    literal: term.Literal

    def __init__(self, literal: LiteralBox | term.Literal | SupportedLiterals) -> None:
        if isinstance(literal, LiteralBox):
            self.literal = literal.literal
        elif isinstance(literal, term.Literal):
            self.literal = literal
        elif isinstance(literal, datetime.datetime | datetime.date):
            raise NotImplementedError
        elif isinstance(literal, SupportedLiterals):
            self.literal = term.Literal(literal)
        else:
            raise TypeError(f"Unhandled type for literal: {literal}")

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return self.literal

    def to_funowl(self) -> str:
        literal = self.literal
        if literal.datatype is None or literal.datatype == XSD.string:
            return f'"{literal.value}"'
        if literal.datatype == XSD.integer:
            return f'"{literal.toPython()}"^^xsd:integer'
        raise NotImplementedError(f"Not implemented for type: {literal.datatype}")

    def to_funowl_args(self) -> str:
        raise RuntimeError


IdentifierBoxOrHint: TypeAlias = IdentifierHint | IdentifierBox
PrimitiveHint: TypeAlias = IdentifierBoxOrHint | term.Literal | SupportedLiterals | LiteralBox
PrimitiveBox: TypeAlias = LiteralBox | IdentifierBox


def _safe_primitive_box(value: PrimitiveHint) -> PrimitiveBox:
    # if it's already boxed, then pass it through
    if isinstance(value, PrimitiveBox):
        return value
    # note that literal is also a subclass of str,
    # so it needs to be cheked first
    if isinstance(value, term.Literal):
        return LiteralBox(value)
    # note that we decided that strings should be parsed
    # by default as a CURIE. If you want to pass a literal
    # through, wrap it with rdflib.Literal
    if isinstance(value, str):
        return IdentifierBox(value)
    if isinstance(value, SupportedLiterals):
        return LiteralBox(value)
    # everything else (e.g., URIRef, Reference) are for identifier boxes
    return IdentifierBox(value)


def _make_sequence(graph: Graph, members: Iterable[Box]) -> term.Node:
    """Make a sequence."""
    return _make_sequence_nodes(graph, [m.to_rdflib_node(graph) for m in members])


def _make_sequence_nodes(graph: Graph, members: list[term.Node]) -> term.Node:
    """Make a sequence."""
    if not members:
        return RDF.nil
    node = term.BNode()
    collection.Collection(graph, node, members)
    return node


"""Section 5"""

DeclarationType: TypeAlias = typing.Literal[
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


class Declaration(Box):
    """Declarations."""

    def __init__(self, node: IdentifierBoxOrHint, dtype: DeclarationType) -> None:
        self.node = IdentifierBox(node)
        self.dtype = dtype

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = self.node.to_rdflib_node(graph)
        graph.add((node, RDF.type, type_to_uri[self.dtype]))
        return node

    def to_funowl(self) -> str:
        return f"Declaration( {self.dtype}( {self.node.to_funowl()} ) )"

    def to_funowl_args(self) -> str:
        raise NotImplementedError


"""
Section 6: Property Expressions
"""


class ObjectPropertyExpression(Box):
    """A model representing `6.1 "Object Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_objectproperty.gif
    """

    @classmethod
    def safe(cls, ope: ObjectPropertyExpression | IdentifierBoxOrHint) -> ObjectPropertyExpression:
        if isinstance(ope, IdentifierBoxOrHint):
            return SimpleObjectPropertyExpression(ope)
        return ope


class SimpleObjectPropertyExpression(IdentifierBox, ObjectPropertyExpression):
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
        self, object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, OWL.inverseOf, self.object_property_expression.to_rdflib_node(graph)))
        return node

    def to_funowl_args(self) -> str:
        return self.object_property_expression.to_funowl()


class DataPropertyExpression(Box):  # 6.2
    """A model representing `6.2 "Data Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_dataproperty.gif
    """

    @classmethod
    def safe(cls, dpe: DataPropertyExpression | IdentifierBoxOrHint) -> DataPropertyExpression:
        if isinstance(dpe, IdentifierBoxOrHint):
            return SimpleDataPropertyExpression(dpe)
        return dpe


class SimpleDataPropertyExpression(IdentifierBox, DataPropertyExpression):
    """A simple data property expression represented by an IRI/CURIE."""


"""
Section 7: Data Ranges
"""


class DataRange(Box):
    """A model representing `7 "Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Datatypes>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_datarange.gif
    """

    @classmethod
    def safe(cls, data_range: DataRange | IdentifierBoxOrHint) -> DataRange:
        if isinstance(data_range, IdentifierBoxOrHint):
            return SimpleDateRange(data_range)
        return data_range


class SimpleDateRange(IdentifierBox, DataRange):
    """A simple data range represented by an IRI/CURIE."""


class _ListDataRange(DataRange):
    """An abstract model for data intersection and union expressions."""

    property_type: ClassVar[term.URIRef]

    def __init__(self, data_ranges: Sequence[DataRange | IdentifierBoxOrHint]):
        self.data_ranges = [DataRange.safe(dr) for dr in data_ranges]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        return _list_to_funowl(self.data_ranges)


class DataIntersectionOf(_ListDataRange):
    """A data range defined in `7.1 "Intersection of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Data_Ranges>`_.

    The following data range contains exactly the integer 0:

    >>> DataIntersectionOf("xsd:nonNegativeInteger", "xsd:nonPositiveInteger")
    """

    property_type: ClassVar[term.URIRef] = OWL.intersectionOf


class DataUnionOf(_ListDataRange):
    """A data range defined in `7.2 "Union of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Union_of_Data_Ranges>`_.

    The following data range contains all strings and all integers:

    >>> DataUnionOf("xsd:string", "xsd:integer")
    """

    property_type: ClassVar[term.URIRef] = OWL.unionOf


class DataComplementOf(DataRange):
    """A data range defined in `7.3 Complement of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Complement_of_Data_Ranges>`_.

    The following complement data range contains literals that are not positive integers:

    >>> DataComplementOf("xsd:positiveInteger")

    The following contains all non-zero integers:

    >>> DataComplementOf(DataIntersectionOf("xsd:nonNegativeInteger", "xsd:nonPositiveInteger"))
    """

    def __init__(self, data_range: DataRange | IdentifierBoxOrHint):
        self.data_range = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, OWL.datatypeComplementOf, self.data_range.to_rdflib_node(graph)))
        return node

    def to_funowl_args(self) -> str:
        return self.data_range.to_funowl()


class DataOneOf(DataRange):
    """A data range defined in `7.4 Enumeration of Literals" <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Literals>`_.

    The following data range contains exactly two literals: the string "Peter" and the integer one.

    >>> DataOneOf(["Peter", 1])

    This can be specified more explicitly with :class:`rdflib.Literal`:

    >>> DataOneOf(["Peter", rdflib.Literal(1, datatype=XSD.nonNegativeInteger)])
    """

    def __init__(self, literals: Sequence[term.Literal | SupportedLiterals]):
        self.literals = [LiteralBox(literal) for literal in literals]

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        literal_nodes = [literal.to_rdflib_node(graph) for literal in self.literals]
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, OWL.oneOf, _make_sequence_nodes(graph, literal_nodes)))
        return node

    def to_funowl_args(self) -> str:
        return _list_to_funowl(self.literals)


class DatatypeRestriction(DataRange):
    """A data range defined in `7.5 Datatype Restrictions " <https://www.w3.org/TR/owl2-syntax/#Datatype_Restrictions>`_.

    The following data range contains exactly the integers 5, 6, 7, 8, and 9:

    >>> DatatypeRestriction("xsd:integer", [("xsd:minInclusive", 5), ("xsd:maxExclusive", 10)])
    """

    pairs: list[tuple[IdentifierBox, LiteralBox]]

    def __init__(
        self,
        dtype: IdentifierBoxOrHint,
        pairs: list[tuple[IdentifierBoxOrHint, term.Literal | SupportedLiterals]],
    ) -> None:
        self.dtype = IdentifierBox(dtype)
        self.pairs = [(IdentifierBox(facet), LiteralBox(value)) for facet, value in pairs]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        pairs_funowl = " ".join(
            f"{facet.to_funowl()} {value.to_funowl()}" for facet, value in self.pairs
        )
        return f"{self.dtype.to_funowl()} {pairs_funowl}"


"""
`Section 8: Class Expressions <https://www.w3.org/TR/owl2-syntax/#Class_Expressions>`_
"""


class ClassExpression(Box):
    """An abstract model representing class expressions."""

    @classmethod
    def safe(cls, class_expresion: ClassExpression | IdentifierBoxOrHint) -> ClassExpression:
        if isinstance(class_expresion, IdentifierBoxOrHint):
            return SimpleClassExpression(class_expresion)
        return class_expresion


class SimpleClassExpression(IdentifierBox, ClassExpression):
    """A simple class expression represented by an IRI/CURIE."""


class _ObjectList(ClassExpression):
    """An abstract model for class expressions defined by lists.

    Defined in `8.1 Propositional Connectives and Enumeration of
    Individuals <Propositional_Connectives_and_Enumeration_of_Individuals>`_

    .. image:: https://www.w3.org/TR/owl2-syntax/C_propositional.gif
    """

    property_type: ClassVar[term.URIRef]

    def __init__(self, class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint]) -> None:
        """Initialize the model with a list of class expressions."""
        if len(class_expressions) < 2:
            raise ValueError("must have at least two class expressions")
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, self.property_type, _make_sequence(graph, self.class_expressions)))
        return node

    def to_funowl_args(self) -> str:
        return _list_to_funowl(self.class_expressions)


class ObjectIntersectionOf(_ObjectList):
    """A class expression defined in `8.1.1 Intersection of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Class_Expressions>`_.

    Consider the ontology consisting of the following axioms.

    >>> ClassAssertion("a:Dog", "a:Brian")  # Brian is a dog.
    >>> ClassAssertion("a:CanTalk" "a:Brian")  # Brian can talk.

    The following class expression describes all dogs that can talk;
    furthermore, ``a:Brian`` is classified as its instance.

    >>> ObjectIntersectionOf("a:Dog", "a:CanTalk")
    """

    property_type: ClassVar[term.URIRef] = OWL.intersectionOf


class ObjectUnionOf(_ObjectList):
    """A class expression defined in `8.1.2 Union of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Union_of_Class_Expressions>`_.

    Consider the ontology consisting of the following axioms.

    >>> ClassAssertion("a:Man", "a:Peter")  # Peter is a man.
    >>> ClassAssertion("a:Woman", "a:Lois")  # Lois is a woman.

    The following class expression describes all individuals that are instances of either
    ``a:Man`` or ``a:Woman``; furthermore, both ``a:Peter`` and ``a:Lois`` are classified
    as its instances:

    >>> ObjectUnionOf("a:Man", "a:Woman")
    """

    property_type: ClassVar[term.URIRef] = OWL.unionOf


class ObjectComplementOf(ClassExpression):
    """A class expression defined in `8.1.3 Complement of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Complement_of_Class_Expressions>`_.

    Example 1
    ---------
    Consider the ontology consisting of the following axioms.

    >>> DisjointClasses("a:Man", "a:Woman")  # Nothing can be both a man and a woman.
    >>> ClassAssertion("a:Woman", "a:Lois")  # Lois is a woman.

    The following class expression describes all things that are not instances of a:Man:

    >>> ObjectComplementOf("a:Man")

    Example 2
    ---------
    OWL 2 has open-world semantics, so negation in OWL 2 is the same as in classical
    (first-order) logic. To understand open-world semantics, consider the ontology
    consisting of the following assertion.

    >>> ClassAssertion("a:Dog", "a:Brian")  # Brian is a dog.

    One might expect ``a:Brian`` to be classified as an instance of
    the following class expression:

    >>> ObjectComplementOf("a:Bird")

    However, because of the OWL reasoning, this can't be concluded
    """

    def __init__(self, class_expression: ClassExpression | IdentifierBoxOrHint) -> None:
        """Initialize the model with a single class expression."""
        self.class_expression = ClassExpression.safe(class_expression)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, OWL.complementOf, self.class_expression.to_rdflib_node(graph)))
        return node

    def to_funowl_args(self) -> str:
        return self.class_expression.to_funowl()


class ObjectOneOf(_ObjectList):
    """A class expression defined in `8.1.4 Enumeration of Individuals <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Individuals>`_."""

    # TODO restrict to individuals

    property_type: ClassVar[term.URIRef] = OWL.oneOf


def _owl_rdf_restriction(
    graph: Graph, prop: Box, target_property: term.URIRef, target: Box | term.Literal
) -> term.BNode:
    # this is shared between several class expressions
    node = term.BNode()
    graph.add((node, RDF.type, OWL.Restriction))
    graph.add((node, OWL.onProperty, prop.to_rdflib_node(graph)))
    if isinstance(target, Box):
        graph.add((node, target_property, target.to_rdflib_node(graph)))
    else:
        graph.add((node, target_property, target))

    return node


class _ObjectValuesFrom(ClassExpression):
    object_expression_predicate: ClassVar[term.URIRef]

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        class_expression: ClassExpression | IdentifierBoxOrHint,
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

    def to_funowl_args(self) -> str:
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
    individual: IdentifierBox

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        individual: IdentifierBoxOrHint,
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.individual = IdentifierBox(individual)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _owl_rdf_restriction(
            graph, self.object_property_expression, OWL.hasValue, self.individual
        )

    def to_funowl_args(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.individual.to_funowl()}"


class ObjectHasSelf(ClassExpression):
    """A class expression defined in `8.2.4 Self-Restriction <https://www.w3.org/TR/owl2-syntax/#Self-Restriction>`_."""

    def __init__(
        self, object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint
    ) -> None:
        """Initialize the model with a property expression."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _owl_rdf_restriction(
            graph, self.object_property_expression, OWL.hasSelf, term.Literal(True)
        )

    def to_funowl_args(self) -> str:
        return self.object_property_expression.to_funowl()


class _Cardinality(ClassExpression):
    """A helper class for object and data cardinality constraints."""

    property_qualified: ClassVar[term.URIRef]
    property_unqualified: ClassVar[term.URIRef]
    property_type: ClassVar[term.URIRef]

    def __init__(
        self, n: int, property_expression: Box, object_expression: Box | None = None
    ) -> None:
        self.n = n
        self.property_expression = property_expression
        self.object_expression = object_expression

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        graph.add((node, OWL.onProperty, self.property_expression.to_rdflib_node(graph)))
        literal = term.Literal(str(self.n), datatype=XSD.nonNegativeInteger)
        if self.object_expression is not None:
            graph.add((node, self.property_qualified, literal))
            graph.add((node, self.property_type, self.object_expression.to_rdflib_node(graph)))
        else:
            graph.add((node, self.property_unqualified, literal))
        return node

    def to_funowl_args(self) -> str:
        inside = f"{self.n} {self.property_expression.to_funowl()}"
        if self.object_expression is not None:
            inside += f" {self.object_expression.to_funowl()}"
        return inside


class _ObjectCardinality(_Cardinality):
    """A grouping class for object cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    property_type: ClassVar[term.URIRef] = OWL.onClass

    def __init__(
        self,
        n: int,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        class_expression: ClassExpression | IdentifierBoxOrHint | None = None,
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
        data_property_expressions: list[DataPropertyExpression | IdentifierBoxOrHint],
        data_range: DataRange | IdentifierBoxOrHint,
    ) -> None:
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        self.data_range = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        if len(self.data_property_expressions) >= 2:
            p_o = OWL.onProperties, _make_sequence(graph, self.data_property_expressions)
        else:
            p_o = OWL.onProperty, self.data_property_expressions[0].to_rdflib_node(graph)
        graph.add((node, self.property_type, self.data_range.to_rdflib_node(graph)))
        graph.add((node, *p_o))
        return node

    def to_funowl_args(self) -> str:
        return _list_to_funowl((*self.data_property_expressions, self.data_range))


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
        data_property_expressions: XorList[DataPropertyExpression | IdentifierBoxOrHint],
        literal: term.Literal,
    ) -> None:
        if isinstance(data_property_expressions, DataPropertyExpression | IdentifierBoxOrHint):
            data_property_expressions = [data_property_expressions]
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        self.literal = LiteralBox(literal)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        # TODO reuse from _DataValuesFrom
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        first = _list_to_funowl(self.data_property_expressions)
        return f"{first} {self.literal.to_funowl()}"


class _DataCardinality(_Cardinality):
    """A grouping class for data cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    property_type: ClassVar[term.URIRef] = OWL.onDataRange

    def __init__(
        self,
        n: int,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        data_range: DataRange | IdentifierBoxOrHint | None = None,
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


class Axiom(Box, ABC):
    def __init__(self, annotations: list[Annotation] | None = None):
        self.annotations = annotations

    def to_funowl_args(self) -> str:
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
) -> term.BNode:
    graph.add((s, p, o))
    return _add_triple_annotations(graph, s, p, o, annotations=annotations)


def _add_triple_annotations(
    graph: Graph,
    s: term.Node,
    p: term.Node,
    o: term.Node,
    *,
    annotations: Annotations | None = None,
    type: term.URIRef | None = None,
) -> term.BNode:
    node = term.BNode()
    if type:
        graph.add((node, RDF.type, type))
    graph.add((node, OWL.annotatedSource, s))
    graph.add((node, OWL.annotatedProperty, p))
    graph.add((node, OWL.annotatedTarget, o))
    for annotation in annotations or []:
        annotation._add_to_triple(graph, node)
    return node


class SubClassOf(ClassAxiom):  # 9.1.1
    def __init__(
        self,
        child: ClassExpression | IdentifierBoxOrHint,
        parent: ClassExpression | IdentifierBoxOrHint,
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
    class_expression: Sequence[ClassExpression]

    def __init__(
        self,
        class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        if len(class_expressions) < 2:
            raise ValueError
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        rv = term.BNode()
        nodes = [ce.to_rdflib_node(graph) for ce in self.class_expressions]
        for s, o in itt.combinations(nodes, 2):
            _add_triple(graph, s, OWL.equivalentClass, o, self.annotations)
        # TODO connect all triples to this BNode?
        return rv

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
        parent: IdentifierBoxOrHint,
        class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.parent = IdentifierBox(parent)
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.parent.to_rdflib_node(graph),
            OWL.disjointUnionOf,
            _make_sequence(graph, self.class_expressions),
            self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl((self.parent, *self.class_expressions))


"""Section 9.2: Object Property Axioms"""


class ObjectPropertyAxiom(Axiom):
    pass


class ObjectPropertyChain(Box):
    def __init__(
        self, object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierBoxOrHint]
    ):
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def to_funowl_args(self) -> str:
        return _list_to_funowl(self.object_property_expressions)


SubObjectPropertyExpression: TypeAlias = ObjectPropertyExpression | ObjectPropertyChain


class SubObjectPropertyOf(ObjectPropertyAxiom):  # 9.2.1
    child: SubObjectPropertyExpression
    parent: ObjectPropertyExpression

    def __init__(
        self,
        child: SubObjectPropertyExpression | IdentifierBoxOrHint,
        parent: ObjectPropertyExpression | IdentifierBoxOrHint,
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
        object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierBoxOrHint],
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
    graph: Graph, expressions: Iterable[Box], *, annotations: Annotations | None = None
) -> term.BNode:
    nodes = [expression.to_rdflib_node(graph) for expression in expressions]
    for s, o in itt.combinations(nodes, 2):
        _add_triple(graph, s, OWL.equivalentProperty, o, annotations)

    # TODO what to return here?
    return term.BNode()


class EquivalentObjectProperties(_ObjectPropertyList):  # 9.2.2
    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _equivalent_xxx(
            graph, self.object_property_expressions, annotations=self.annotations
        )


def _disjoint_xxx(
    graph: Graph, expressions: Iterable[Box], *, annotations: Annotations | None = None
) -> term.BNode:
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
        child: DataPropertyExpression | IdentifierBoxOrHint,
        parent: DataPropertyExpression | IdentifierBoxOrHint,
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
    data_property_expressions: Sequence[DataPropertyExpression]

    def __init__(
        self,
        data_property_expressions: Sequence[DataPropertyExpression | IdentifierBoxOrHint],
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
    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _equivalent_xxx(
            graph,
            self.data_property_expressions,
            annotations=self.annotations,
        )


class DisjointDataProperties(_DataPropertyList):  # 9.3.2
    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        return _disjoint_xxx(graph, self.data_property_expressions, annotations=self.annotations)


class _BinaryDataPropertyAxiom(DataPropertyAxiom):  # 9.2.4
    property_type: ClassVar[term.Node]

    def __init__(
        self,
        left: DataPropertyExpression | IdentifierBoxOrHint,
        right: ClassExpression | IdentifierBoxOrHint,
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
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
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
    datatype: Box
    data_range: DataRange

    def __init__(
        self,
        datatype: IdentifierBoxOrHint,
        data_range: DataRange | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.datatype = IdentifierBox(datatype)
        self.data_range = DataRange.safe(data_range)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.datatype.to_rdflib_node(graph),
            OWL.equivalentClass,
            self.data_range.to_rdflib_node(graph),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return f"{self.datatype.to_funowl()} {self.data_range.to_funowl()}"


"""Section 9.5: Keys"""


class HasKey(Axiom):
    object_property_expressions: list[ObjectPropertyExpression]
    data_property_expressions: list[DataPropertyExpression]

    def __init__(
        self,
        class_expression: ClassExpression | IdentifierBoxOrHint,
        object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierBoxOrHint],
        data_property_expressions: Sequence[DataPropertyExpression | IdentifierBoxOrHint],
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
        object_and_data_property_expressions: list[
            ObjectPropertyExpression | DataPropertyExpression
        ] = []
        object_and_data_property_expressions.extend(self.object_property_expressions)
        object_and_data_property_expressions.extend(self.data_property_expressions)

        return _add_triple(
            graph,
            self.class_expression.to_rdflib_node(graph),
            OWL.hasKey,
            _make_sequence(graph, object_and_data_property_expressions),
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
        individuals: Sequence[IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.individuals = [IdentifierBox(i) for i in individuals]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return _list_to_funowl(self.individuals)


class SameIndividual(_IndividualListAssertion):  # 9.6.1
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        nodes = [i.to_rdflib_node(graph) for i in self.individuals]
        for s, o in itt.combinations(nodes, 2):
            _add_triple(graph, s, OWL.sameAs, o, annotations=self.annotations)
        # TODO connect this node to triples?
        return term.BNode()


class DifferentIndividuals(_IndividualListAssertion):  # 9.6.2
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        nodes = [i.to_rdflib_node(graph) for i in self.individuals]
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
        class_expression: ClassExpression | IdentifierBoxOrHint,
        individual: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.class_expression = ClassExpression.safe(class_expression)
        self.individual = IdentifierBox(individual)
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
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        source_individual: IdentifierBoxOrHint,
        target_individual: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.source_individual = IdentifierBox(source_individual)
        self.target_individual = IdentifierBox(target_individual)
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
    source: IdentifierBox
    target: PrimitiveBox

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        source: IdentifierBoxOrHint,
        target: PrimitiveHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.source = IdentifierBox(source)
        self.target = _safe_primitive_box(target)
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.data_property_expression.to_funowl()} {self.source.to_funowl()} {self.target.to_funowl()}"


class DataPropertyAssertion(_DataPropertyAssertion):  # 9.6.6
    """DataPropertyAssertion( a:hasAge a:Meg "17"^^xsd:integer )."""

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.source.to_rdflib_node(graph),
            self.data_property_expression.to_rdflib_node(graph),
            self.target.to_rdflib_node(graph),
            annotations=self.annotations,
        )


class NegativeDataPropertyAssertion(_DataPropertyAssertion):  # 9.6.7
    """NegativeDataPropertyAssertion( a:hasAge a:Meg "5"^^xsd:integer )."""

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple_annotations(
            graph,
            self.source.to_rdflib_node(graph),
            self.data_property_expression.to_rdflib_node(graph),
            self.target.to_rdflib_node(graph),
            annotations=self.annotations,
            type=OWL.NegativePropertyAssertion,
        )


"""Section 10: Annotations"""


class Annotation(Box):  # 10.1
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

    annotation_property: Box
    value: PrimitiveBox

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: list[Annotation] | None = None,
    ):
        self.annotation_property = IdentifierBox(annotation_property)
        self.value = _safe_primitive_box(value)
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise RuntimeError

    def _add_to_triple(self, graph: Graph, node: term.BNode) -> None:
        graph.add(
            (node, self.annotation_property.to_rdflib_node(graph), self.value.to_rdflib_node(graph))
        )
        # TODO recursive nested annotations

    def to_funowl_args(self) -> str:
        end = f"{self.annotation_property.to_funowl()} {self.value.to_funowl()}"
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

    value: PrimitiveBox

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        subject: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: list[Annotation] | None = None,
    ) -> None:
        self.annotation_property = IdentifierBox(annotation_property)
        self.subject = IdentifierBox(subject)
        self.value = _safe_primitive_box(value)
        self.annotations = annotations

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _add_triple(
            graph,
            self.subject.to_rdflib_node(graph),
            self.annotation_property.to_rdflib_node(graph),
            self.value.to_rdflib_node(graph),
            annotations=self.annotations,
        )

    def _funowl_inside_2(self) -> str:
        return " ".join(
            (
                self.annotation_property.to_funowl(),
                self.subject.to_funowl(),
                self.value.to_funowl(),
            )
        )


class SubAnnotationPropertyOf(AnnotationAxiom):  # 10.2.2
    """An annotation axiom defined in `10.2.2 Annotation Subproperties <https://www.w3.org/TR/owl2-syntax/#Annotation_Subproperties>`_."""

    def __init__(
        self,
        child: IdentifierBoxOrHint,
        parent: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        self.child = IdentifierBox(child)
        self.parent = IdentifierBox(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.child.to_rdflib_node(graph)
        o = self.parent.to_rdflib_node(graph)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class AnnotationPropertyTypingAxiom(AnnotationAxiom):
    """A helper class that defines shared functionality between annotation property domains and ranges."""

    property_type: ClassVar[term.URIRef]
    annotation_property: IdentifierBox
    value: PrimitiveBox

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: Annotations | None = None,
        property: term.Node,
    ) -> None:
        self.annotation_property = IdentifierBox(annotation_property)
        self.value = _safe_primitive_box(value)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        s = self.annotation_property.to_rdflib_node(graph)
        o = self.value.to_rdflib_node(graph)
        return _add_triple(graph, s, self.property_type, o, self.annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.annotation_property.to_funowl()} {self.value.to_funowl()}"


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
