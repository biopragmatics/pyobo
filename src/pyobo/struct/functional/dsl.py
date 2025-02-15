"""A DSL for functional OWL."""

from __future__ import annotations

import datetime
import itertools as itt
import typing
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from typing import ClassVar, TypeAlias

import rdflib.namespace
from curies import Converter, Reference
from rdflib import OWL, RDF, RDFS, XSD, Graph, collection, term

from pyobo.struct.functional.utils import list_to_funowl
from pyobo.struct.reference import Reference as PyOBOReference
from pyobo.struct.reference import Referenced, get_preferred_prefix
from pyobo.struct.struct_utils import OBOLiteral

from .utils import FunctionalOWLSerializable, RDFNodeSerializable

__all__ = [
    "Annotation",
    "AnnotationAssertion",
    "AnnotationAxiom",
    "AnnotationProperty",
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
    "ReflexiveObjectProperty",
    "SameIndividual",
    "SubAnnotationPropertyOf",
    "SubClassOf",
    "SubDataPropertyOf",
    "SubObjectPropertyExpression",
    "SubObjectPropertyOf",
    "SymmetricObjectProperty",
    "TransitiveObjectProperty",
    "l",
]


def l(value) -> term.Literal:  # noqa:E743
    """Get a literal."""
    return term.Literal(value)


#: These are the literals that can be automatically converted to and from RDFLib
SupportedLiterals: TypeAlias = int | float | bool | str | datetime.date | datetime.datetime

#: A partial hint for something that can be turned into an :class:`IdentifierBox`.
#: Here, a string gets interpreted into a CURIE using :meth:`curies.Reference.from_curie`
IdentifierHint = term.URIRef | Reference | Referenced | str


class Box(FunctionalOWLSerializable, RDFNodeSerializable):
    """A model for objects that can be represented as nodes in RDF and Functional OWL."""


def obo_literal_to_rdflib(obo_literal: OBOLiteral, converter: Converter) -> rdflib.Literal:
    """Expand the OBO literal."""
    iri = converter.expand(obo_literal.datatype.curie, strict=True)
    return rdflib.Literal(obo_literal.value, datatype=rdflib.URIRef(iri))


class IdentifierBox(Box):
    """A simple wrapper around CURIEs and IRIs."""

    identifier: term.URIRef | Reference

    def __init__(self, identifier: IdentifierBoxOrHint) -> None:
        """Initialize the identifier box with a URIRef, Reference, or string representing a CURIE."""
        if isinstance(identifier, Referenced):
            identifier = identifier.reference
        if isinstance(identifier, IdentifierBox):
            self.identifier = identifier.identifier
        # make sure to check for URIRef first,
        # since it's also a subclass of str
        elif isinstance(identifier, term.URIRef):
            self.identifier = identifier
        elif isinstance(identifier, str):
            self.identifier = Reference.from_curie(identifier)
        elif isinstance(identifier, PyOBOReference):
            # it doesn't matter we're potentially throwing away the name,
            # since this annotation gets put in OFN in a different place
            self.identifier = Reference(
                prefix=get_preferred_prefix(identifier), identifier=identifier.identifier
            )
        elif isinstance(identifier, Reference):
            self.identifier = identifier
        else:
            raise TypeError(f"can not make an identifier box from: {identifier}")

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this identifier for RDF, using the converter to convert a CURIE if appropriate."""
        if isinstance(self.identifier, term.URIRef):
            return self.identifier
        # TODO make more efficient
        iri = converter.expand(self.identifier.curie, strict=True)
        return term.URIRef(iri)

    def to_funowl(self) -> str:
        """Represent this identifier for functional OWL."""
        if isinstance(self.identifier, term.URIRef):
            return f"<{self.identifier}>"
        if any(c in self.identifier.identifier for c in "()"):
            raise ValueError(f"Can't encode CURIE with parentheses to OFN: {self.identifier}")
        return self.identifier.curie

    def to_funowl_args(self) -> str:  # pragma: no cover
        """Get the inside of the functional OWL tag representing the identifier (unused)."""
        raise RuntimeError


class LiteralBox(Box):
    """A simple wrapper around a literal."""

    literal: term.Literal
    _namespace_manager: ClassVar[rdflib.namespace.NamespaceManager] = Graph().namespace_manager
    _converter: ClassVar[Converter] = Converter.from_rdflib(_namespace_manager)

    def __init__(self, literal: LiteralBoxOrHint, language: str | None = None) -> None:
        """Initialize the literal box with a RDFlib literal or Python primitive.."""
        if literal is None:
            raise ValueError
        if isinstance(literal, LiteralBox):
            self.literal = literal.literal
        elif isinstance(literal, term.Literal):
            self.literal = literal
        elif isinstance(literal, bool):
            self.literal = term.Literal(str(literal).lower(), datatype=XSD.boolean)
        elif isinstance(literal, int):
            self.literal = term.Literal(literal, datatype=XSD.integer)
        elif isinstance(literal, float):
            self.literal = term.Literal(literal, datatype=XSD.decimal)
        elif isinstance(literal, str):
            self.literal = term.Literal(literal, lang=language)
        elif isinstance(literal, datetime.date):
            self.literal = term.Literal(literal, datatype=XSD.date)
        elif isinstance(literal, datetime.datetime):
            self.literal = term.Literal(literal, datatype=XSD.dateTime)
        elif isinstance(literal, OBOLiteral):
            self.literal = obo_literal_to_rdflib(literal, self._converter)
        else:
            raise TypeError(f"Unhandled type for literal: {literal}")

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Literal:
        """Represent this literal for RDF."""
        return self.literal

    def to_funowl(self) -> str:
        """Represent this literal for functional OWL."""
        return self.literal.n3(self._namespace_manager)

    def to_funowl_args(self) -> str:  # pragma: no cover
        """Get the inside of the functional OWL tag representing the literal (unused)."""
        raise RuntimeError


IdentifierBoxOrHint: TypeAlias = IdentifierHint | IdentifierBox
LiteralBoxOrHint: TypeAlias = LiteralBox | term.Literal | SupportedLiterals | OBOLiteral
PrimitiveHint: TypeAlias = IdentifierBoxOrHint | LiteralBoxOrHint
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
    if isinstance(value, SupportedLiterals | OBOLiteral):
        return LiteralBox(value)
    # everything else (e.g., URIRef, Reference) are for identifier boxes
    return IdentifierBox(value)


def _make_sequence(
    graph: Graph,
    members: Iterable[Box],
    converter: Converter,
    *,
    type_connector_nodes: bool = False,
) -> term.IdentifiedNode:
    """Make a sequence."""
    return _make_sequence_nodes(
        graph,
        [m.to_rdflib_node(graph, converter) for m in members],
        type_connector_nodes=type_connector_nodes,
    )


def _make_sequence_nodes(
    graph: Graph,
    members: Sequence[term.IdentifiedNode | term.Literal],
    *,
    type_connector_nodes: bool = False,
) -> term.IdentifiedNode:
    """Make a sequence."""
    if not members:
        return RDF.nil
    node = term.BNode()
    collection.Collection(graph, node, list(members))
    if type_connector_nodes:
        # This is a weird quirk required for DataOneOf, which for
        # some reason emits `rdf:type rdfs:List` for each element
        for connector_node in _yield_connector_nodes(graph, node):
            graph.add((connector_node, RDF.type, RDF.List))
    return node


def _yield_connector_nodes(
    graph: Graph, start: term.IdentifiedNode
) -> Iterable[term.IdentifiedNode]:
    """Yield all of the nodes representing parts of a collection.

    This is different than simply doing :meth:`rdflib.graph.items`,
    because that function gets the "first" parts - this function
    gets the blank nodes that are representing the prongs in the
    list itself.

    We have to do this because ROBOT implemenents RDF conversion for
    :class:`DataOneOf` strangely, where each blank node in the collection
    gets a triple typing it as a list ``<bnode> rdf:type rdfs:List``
    """
    yield start
    item: term.IdentifiedNode | None = start
    while item := graph.value(item, RDF.rest):  # type:ignore
        if item == RDF.nil:
            break
        yield item


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

    def __init__(self, node: IdentifierBoxOrHint, type: DeclarationType) -> None:
        """Initialize the declaration with a given identifier and type."""
        self.node = IdentifierBox(node)
        self.type = type

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this declaration for RDF."""
        node = self.node.to_rdflib_node(graph, converter)
        graph.add((node, RDF.type, type_to_uri[self.type]))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the declaration."""
        return f"{self.type}({self.node.to_funowl()})"


"""
Section 6: Property Expressions
"""


class ObjectPropertyExpression(Box):
    """A model representing `6.1 "Object Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_objectproperty.gif
    """

    @classmethod
    def safe(cls, ope: ObjectPropertyExpression | IdentifierBoxOrHint) -> ObjectPropertyExpression:
        """Pass through a pre-instantiated object property expression, or create a simple one for an identifier."""
        if isinstance(ope, IdentifierBoxOrHint):
            return SimpleObjectPropertyExpression(ope)
        return ope


class SimpleObjectPropertyExpression(IdentifierBox, ObjectPropertyExpression):
    """A simple object property expression represented by an IRI/CURIE."""

    #: A set of built-in object properties that shouldn't be re-defined, since they
    #: appear in Table 3 of https://www.w3.org/TR/owl2-syntax/#IRIs.
    _SKIP: ClassVar[set[term.Node]] = {OWL.topObjectProperty, OWL.bottomObjectProperty}

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this object property identifier for RDF."""
        node = super().to_rdflib_node(graph, converter)
        if node in self._SKIP:
            return node
        graph.add((node, RDF.type, OWL.ObjectProperty))
        return node


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

    object_property: IdentifierBox

    def __init__(self, object_property: IdentifierBoxOrHint) -> None:
        """Instantiate an inverse object property."""
        # note that this can't be an expression - it has to be a defined thing.
        # further, we can't use SimpleObjectPropertyExpression because
        # we're trying to stay consistent with OWLAPI, and it sometimes doesn't
        # automatically assert the enclosed property as a owl:ObjectProperty,
        # e.g., inside ObjectMaxCardinality (not) and inside SubjectPropertyOf (does)
        # see https://github.com/owlcs/owlapi/issues/1161
        self.object_property = IdentifierBox(object_property)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Get a node representing the inverse object property."""
        node = term.BNode()
        graph.add((node, OWL.inverseOf, self.object_property.to_rdflib_node(graph, converter)))
        return node

    def declare_wrapped_ope(self, graph: Graph, converter: Converter) -> None:
        """Declare the wrapped object property."""
        graph.add(
            (self.object_property.to_rdflib_node(graph, converter), RDF.type, OWL.ObjectProperty)
        )

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the inverse object property."""
        return self.object_property.to_funowl()


class DataPropertyExpression(Box):
    """A model representing `6.2 "Data Property Expressions" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Expressions>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_dataproperty.gif
    """

    @classmethod
    def safe(cls, dpe: DataPropertyExpression | IdentifierBoxOrHint) -> DataPropertyExpression:
        """Pass through a pre-instantiated data property expression, or create a simple one for an identifier."""
        if isinstance(dpe, IdentifierBoxOrHint):
            return SimpleDataPropertyExpression(dpe)
        return dpe


class SimpleDataPropertyExpression(IdentifierBox, DataPropertyExpression):
    """A simple data property expression represented by an IRI/CURIE."""

    #: A set of built-in data properties that shouldn't be re-defined, since they
    #: appear in Table 3 of https://www.w3.org/TR/owl2-syntax/#IRIs.
    _SKIP: ClassVar[set[term.URIRef]] = {OWL.topDataProperty, OWL.bottomDataProperty}

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this data property identifier for RDF."""
        node = super().to_rdflib_node(graph, converter)
        if node in self._SKIP:
            return node
        graph.add((node, RDF.type, OWL.DatatypeProperty))
        return node


"""
Section 7: Data Ranges
"""


class DataRange(Box):
    """A model representing `7 "Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Datatypes>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_datarange.gif
    """

    @classmethod
    def safe(cls, data_range: DataRange | IdentifierBoxOrHint) -> DataRange:
        """Pass through a pre-instantiated data range, or create a simple one for an identifier."""
        if isinstance(data_range, IdentifierBoxOrHint):
            return SimpleDateRange(data_range)
        return data_range


class SimpleDateRange(IdentifierBox, DataRange):
    """A simple data range represented by an IRI/CURIE."""

    # TODO add skip to RDF node output for builtin data types?


class _ListDataRange(DataRange):
    """An abstract model for data intersection and union expressions."""

    property_type: ClassVar[term.URIRef]
    data_ranges: Sequence[DataRange]

    def __init__(self, data_ranges: Sequence[DataRange | IdentifierBoxOrHint]) -> None:
        """Initialize this list of data ranges."""
        self.data_ranges = [DataRange.safe(dr) for dr in data_ranges]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this list of data range for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, self.property_type, _make_sequence(graph, self.data_ranges, converter)))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the data range."""
        return list_to_funowl(self.data_ranges)


class DataIntersectionOf(_ListDataRange):
    """A data range defined in `7.1 "Intersection of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Data_Ranges>`_.

    The following data range contains exactly the integer 0:

    >>> DataIntersectionOf(["xsd:nonNegativeInteger", "xsd:nonPositiveInteger"])
    """

    property_type: ClassVar[term.URIRef] = OWL.intersectionOf


class DataUnionOf(_ListDataRange):
    """A data range defined in `7.2 "Union of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Union_of_Data_Ranges>`_.

    The following data range contains all strings and all integers:

    >>> DataUnionOf(["xsd:string", "xsd:integer"])
    """

    property_type: ClassVar[term.URIRef] = OWL.unionOf


class DataComplementOf(DataRange):
    """A data range defined in `7.3 Complement of Data Ranges" <https://www.w3.org/TR/owl2-syntax/#Complement_of_Data_Ranges>`_.

    The following complement data range contains literals that are not positive integers:

    >>> DataComplementOf("xsd:positiveInteger")

    The following contains all non-zero integers:

    >>> DataComplementOf(DataIntersectionOf(["xsd:nonNegativeInteger", "xsd:nonPositiveInteger"]))
    """

    data_range: DataRange

    def __init__(self, data_range: DataRange | IdentifierBoxOrHint):
        """Initialize a complement of a data range using another data range."""
        self.data_range = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this complement of a data range for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add(
            (node, OWL.datatypeComplementOf, self.data_range.to_rdflib_node(graph, converter))
        )
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the complement of data range."""
        return self.data_range.to_funowl()


class DataOneOf(DataRange):
    """A data range defined in `7.4 Enumeration of Literals" <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Literals>`_.

    The following data range contains exactly two literals: the string "Peter" and the integer one.

    >>> DataOneOf(["Peter", 1])

    This can be specified more explicitly with :class:`rdflib.Literal`:

    >>> import rdflib
    >>> DataOneOf(["Peter", rdflib.Literal(1, datatype=XSD.nonNegativeInteger)])
    """

    literals: Sequence[LiteralBox]

    def __init__(self, literals: Sequence[LiteralBoxOrHint]):
        """Initialize an enumeration of literals."""
        self.literals = [LiteralBox(literal) for literal in literals]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this enumeration of literals for RDF."""
        node = term.BNode()
        literal_nodes = [literal.to_rdflib_node(graph, converter) for literal in self.literals]
        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add(
            (node, OWL.oneOf, _make_sequence_nodes(graph, literal_nodes, type_connector_nodes=True))
        )
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the enumeration of literals."""
        return list_to_funowl(self.literals)


class DatatypeRestriction(DataRange):
    """A data range defined in `7.5 Datatype Restrictions " <https://www.w3.org/TR/owl2-syntax/#Datatype_Restrictions>`_.

    The following data range contains exactly the integers 5, 6, 7, 8, and 9:

    >>> DatatypeRestriction("xsd:integer", [("xsd:minInclusive", 5), ("xsd:maxExclusive", 10)])
    """

    datatype: IdentifierBox
    pairs: list[tuple[IdentifierBox, LiteralBox]]

    def __init__(
        self,
        datatype: IdentifierBoxOrHint,
        pairs: list[tuple[IdentifierBoxOrHint, LiteralBoxOrHint]],
    ) -> None:
        """Initialize a datatype restriction.

        :param datatype: The base datatype
        :param pairs: A list of pairs of restrictions (e.g., ``xsd:minInclusive``) and literal values
        """
        self.datatype = IdentifierBox(datatype)
        self.pairs = [(IdentifierBox(facet), LiteralBox(value)) for facet, value in pairs]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this datatype restriction for RDF."""
        node = term.BNode()

        restrictions: list[term.BNode] = []
        for facet, value in self.pairs:
            restriction = term.BNode()
            graph.add(
                (
                    restriction,
                    facet.to_rdflib_node(graph, converter),
                    value.to_rdflib_node(graph, converter),
                )
            )
            restrictions.append(restriction)

        graph.add((node, RDF.type, RDFS.Datatype))
        graph.add((node, OWL.onDatatype, self.datatype.to_rdflib_node(graph, converter)))
        graph.add((node, OWL.withRestrictions, _make_sequence_nodes(graph, restrictions)))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the datatype restriction."""
        pairs_funowl = " ".join(
            f"{facet.to_funowl()} {value.to_funowl()}" for facet, value in self.pairs
        )
        return f"{self.datatype.to_funowl()} {pairs_funowl}"


"""
`Section 8: Class Expressions <https://www.w3.org/TR/owl2-syntax/#Class_Expressions>`_
"""


class ClassExpression(Box):
    """An abstract model representing `class expressions <https://www.w3.org/TR/owl2-syntax/#Class_Expressions>`_."""

    @classmethod
    def safe(cls, class_expresion: ClassExpression | IdentifierBoxOrHint) -> ClassExpression:
        """Pass through a pre-instantiated class expression, or create a simple one for an identifier."""
        if isinstance(class_expresion, IdentifierBoxOrHint):
            return SimpleClassExpression(class_expresion)
        return class_expresion


class SimpleClassExpression(IdentifierBox, ClassExpression):
    """A simple class expression represented by an IRI/CURIE."""

    #: A set of built-in classes that shouldn't be re-defined, since they
    #: appear in Table 3 of https://www.w3.org/TR/owl2-syntax/#IRIs.
    _SKIP: ClassVar[set[term.Node]] = {OWL.Thing, OWL.Nothing}

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this class identifier for RDF."""
        node = super().to_rdflib_node(graph, converter)
        if node in self._SKIP:
            # i.e., don't add extra annotations for these
            return node
        graph.add((node, RDF.type, OWL.Class))
        return node


class _ObjectList(ClassExpression):
    """An abstract model for class expressions defined by lists.

    Defined in `8.1 Propositional Connectives and Enumeration of
    Individuals <Propositional_Connectives_and_Enumeration_of_Individuals>`_

    .. image:: https://www.w3.org/TR/owl2-syntax/C_propositional.gif
    """

    property_type: ClassVar[term.URIRef]
    class_expressions: Sequence[ClassExpression]

    def __init__(self, class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint]) -> None:
        """Initialize the model with a list of class expressions."""
        if len(class_expressions) < 2:
            raise ValueError("must have at least two class expressions")
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this object list identifier for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add(
            (node, self.property_type, _make_sequence(graph, self.class_expressions, converter))
        )
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the object list."""
        return list_to_funowl(self.class_expressions)


class ObjectIntersectionOf(_ObjectList):
    """A class expression defined in `8.1.1 Intersection of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Class_Expressions>`_.

    Consider the ontology consisting of the following axioms.

    >>> ClassAssertion("a:Dog", "a:Brian")  # Brian is a dog.
    >>> ClassAssertion("a:CanTalk", "a:Brian")  # Brian can talk.

    The following class expression describes all dogs that can talk;
    furthermore, ``a:Brian`` is classified as its instance.

    >>> ObjectIntersectionOf(["a:Dog", "a:CanTalk"])
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

    >>> ObjectUnionOf(["a:Man", "a:Woman"])
    """

    property_type: ClassVar[term.URIRef] = OWL.unionOf


class ObjectComplementOf(ClassExpression):
    """A class expression defined in `8.1.3 Complement of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Complement_of_Class_Expressions>`_.

    Example 1
    ---------
    Consider the ontology consisting of the following axioms.

    >>> DisjointClasses(["a:Man", "a:Woman"])  # Nothing can be both a man and a woman.
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

    class_expression: ClassExpression

    def __init__(self, class_expression: ClassExpression | IdentifierBoxOrHint) -> None:
        """Initialize the model with a single class expression."""
        self.class_expression = ClassExpression.safe(class_expression)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this object complement as RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, OWL.complementOf, self.class_expression.to_rdflib_node(graph, converter)))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the complement of class expression."""
        return self.class_expression.to_funowl()


class ObjectOneOf(ClassExpression):
    """A class expression defined in `8.1.4 Enumeration of Individuals <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Individuals>`_."""

    property_type: ClassVar[term.URIRef] = OWL.oneOf
    individuals: Sequence[IdentifierBox]

    def __init__(self, individuals: Sequence[IdentifierBoxOrHint]) -> None:
        """Initialize the model with a list of class expressions."""
        if len(individuals) < 2:
            raise ValueError("must have at least two class expressions")
        self.individuals = [IdentifierBox(i) for i in individuals]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this enumeration of individuals for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        nodes = [i.to_rdflib_node(graph, converter) for i in self.individuals]
        nodes = sorted(nodes, key=str)  # sort is very important to be consistent with OWLAPI!
        for i in nodes:
            graph.add((i, RDF.type, OWL.NamedIndividual))
        graph.add((node, self.property_type, _make_sequence_nodes(graph, nodes)))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the enumeration of individuals."""
        return list_to_funowl(self.individuals)


def get_owl_restriction(
    graph: Graph,
    object_property_expression: ObjectPropertyExpression,
    restriction_predicate: term.URIRef,
    restriction_target: Box | term.Literal | term.IdentifiedNode,
    converter: Converter,
) -> term.BNode:
    """Generate a blank node representing an OWL restriction.

    :param graph: An RDFlib graph
    :param object_property_expression: The object property expression that goes with ``owl:onProperty``
    :param restriction_predicate: The predicate that connects the restriction to the target.
        Can be one of ``owl:someValuesFrom``, ``owl:allValuesFrom``,
        ``owl:hasValue``, ``owl:hasSelf``, or something more exotic
    :param restriction_target: The target reference or literal
    :param converter: The a converter for CURIEs to URIs
    :return: A blank node representing an OWL restriction
    """
    node = term.BNode()
    graph.add((node, RDF.type, OWL.Restriction))
    graph.add((node, OWL.onProperty, object_property_expression.to_rdflib_node(graph, converter)))
    if isinstance(restriction_target, Box):
        graph.add(
            (node, restriction_predicate, restriction_target.to_rdflib_node(graph, converter))
        )
    else:
        graph.add((node, restriction_predicate, restriction_target))
    return node


class _ObjectValuesFrom(ClassExpression):
    #: The predicate used in the OWL restriction, either ``owl:someValuesFrom`` or ``owl:allValuesFrom``
    restriction_predicate: ClassVar[term.URIRef]
    object_property_expression: ObjectPropertyExpression
    class_expression: ClassExpression

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        class_expression: ClassExpression | IdentifierBoxOrHint,
    ) -> None:
        """Instantiate a quantification."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.object_expression = ClassExpression.safe(class_expression)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent this quantification for RDF."""
        return get_owl_restriction(
            graph,
            object_property_expression=self.object_property_expression,
            restriction_predicate=self.restriction_predicate,
            restriction_target=self.object_expression,
            converter=converter,
        )

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the quantification."""
        return f"{self.object_property_expression.to_funowl()} {self.object_expression.to_funowl()}"


class ObjectSomeValuesFrom(_ObjectValuesFrom):
    """A class expression defined in `8.2.1 Existential Quantification <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification>`_."""

    restriction_predicate: ClassVar[term.URIRef] = OWL.someValuesFrom


class ObjectAllValuesFrom(_ObjectValuesFrom):
    """A class expression defined in `8.2.2  Universal Quantification <https://www.w3.org/TR/owl2-syntax/# Universal_Quantification>`_."""

    restriction_predicate: ClassVar[term.URIRef] = OWL.allValuesFrom


class ObjectHasValue(ClassExpression):
    """A class expression defined in `8.2.3 Individual Value Restriction <https://www.w3.org/TR/owl2-syntax/#Individual_Value_Restriction>`_."""

    object_property_expression: ObjectPropertyExpression
    individual: IdentifierBox

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        individual: IdentifierBoxOrHint,
    ) -> None:
        """Instantiate an individual value restriction."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.individual = IdentifierBox(individual)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the individual value restriction for RDF."""
        individual = self.individual.to_rdflib_node(graph, converter)
        graph.add((individual, RDF.type, OWL.NamedIndividual))
        return get_owl_restriction(
            graph,
            object_property_expression=self.object_property_expression,
            restriction_predicate=OWL.hasValue,
            restriction_target=individual,
            converter=converter,
        )

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the individual value restriction."""
        return f"{self.object_property_expression.to_funowl()} {self.individual.to_funowl()}"


class ObjectHasSelf(ClassExpression):
    """A class expression defined in `8.2.4 Self-Restriction <https://www.w3.org/TR/owl2-syntax/#Self-Restriction>`_."""

    object_property_expression: ObjectPropertyExpression

    def __init__(
        self, object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint
    ) -> None:
        """Initialize the model with a property expression."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the self restriction for RDF."""
        return get_owl_restriction(
            graph,
            object_property_expression=self.object_property_expression,
            restriction_predicate=OWL.hasSelf,
            restriction_target=term.Literal(True),
            converter=converter,
        )

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the self-restriction."""
        return self.object_property_expression.to_funowl()


class _Cardinality(ClassExpression):
    """A helper class for object and data cardinality constraints."""

    property_qualified: ClassVar[term.URIRef]
    property_unqualified: ClassVar[term.URIRef]
    property_type: ClassVar[term.URIRef]
    property_expression_type: ClassVar[term.URIRef]  # the datatype for the target_expression

    cardinality: int
    property_expression: Box
    target_expression: Box | None

    def __init__(
        self, cardinality: int, property_expression: Box, target_expression: Box | None = None
    ) -> None:
        """Instantiate the cardinality restriction."""
        self.cardinality = cardinality
        self.property_expression = property_expression
        self.target_expression = target_expression

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Get a node representing the object or data cardinality constraint."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        pe_node = self.property_expression.to_rdflib_node(graph, converter)
        # don't annotate the expression type if it's a blank node
        # (i.e., if the property expression is an ObjectInverseOf)
        if not isinstance(pe_node, term.BNode):
            graph.add((pe_node, RDF.type, self.property_expression_type))
        graph.add((node, OWL.onProperty, pe_node))
        literal = term.Literal(str(self.cardinality), datatype=XSD.nonNegativeInteger)
        if self.target_expression is not None:
            graph.add((node, self.property_qualified, literal))
            graph.add(
                (node, self.property_type, self.target_expression.to_rdflib_node(graph, converter))
            )
        else:
            graph.add((node, self.property_unqualified, literal))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the cardinality constraint."""
        inside = f"{self.cardinality} {self.property_expression.to_funowl()}"
        if self.target_expression is not None:
            inside += f" {self.target_expression.to_funowl()}"
        return inside


class _ObjectCardinality(_Cardinality):
    """A grouping class for object cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.

    .. image:: https://www.w3.org/TR/owl2-syntax/C_objectcardinality.gif
    """

    property_type: ClassVar[term.URIRef] = OWL.onClass
    property_expression_type: ClassVar[term.URIRef] = OWL.ObjectProperty
    property_expression: ObjectPropertyExpression
    target_expression: ClassExpression | None

    def __init__(
        self,
        cardinality: int,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        class_expression: ClassExpression | IdentifierBoxOrHint | None = None,
    ) -> None:
        """Instantiate an object cardinality restriction."""
        super().__init__(
            cardinality=cardinality,
            property_expression=ObjectPropertyExpression.safe(object_property_expression),
            target_expression=ClassExpression.safe(class_expression)
            if class_expression is not None
            else None,
        )

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the object cardinality restriction for RDF."""
        node = super().to_rdflib_node(graph, converter)
        # we're special-casing this because of the inconsistent way that OWLAPI
        # adds type assertions when using ObjectInverseOf (for some reason,
        # it doesn't generate them inside EquivalentClasses)
        if isinstance(self.property_expression, ObjectInverseOf):
            self.property_expression.declare_wrapped_ope(graph, converter)
        return node


class ObjectMinCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.1 Minimum Cardinality <https://www.w3.org/TR/owl2-syntax/#Minimum_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.minQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.minCardinality


class ObjectMaxCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.2 Maximum Cardinality <https://www.w3.org/TR/owl2-syntax/#Maximum_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.maxQualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.maxCardinality


class ObjectExactCardinality(_ObjectCardinality):
    """A class expression defined in `8.3.2 Exact Cardinality <https://www.w3.org/TR/owl2-syntax/#Exact_Cardinality>`_."""

    property_qualified: ClassVar[term.URIRef] = OWL.qualifiedCardinality
    property_unqualified: ClassVar[term.URIRef] = OWL.cardinality


class _DataValuesFrom(ClassExpression):
    """A class expression defined in https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2."""

    property_type: ClassVar[term.URIRef]
    data_property_expressions: Sequence[DataPropertyExpression]
    data_range: DataRange

    def __init__(
        self,
        data_property_expressions: list[DataPropertyExpression | IdentifierBoxOrHint],
        data_range: DataRange | IdentifierBoxOrHint,
    ) -> None:
        """Instantiate a data values existential quantification."""
        if not data_property_expressions:
            raise ValueError
        if len(data_property_expressions) >= 2:
            raise NotImplementedError(
                "while the OWL 2 spec states that there can be multiple data property "
                "expressions, there is no explanation on what should be done if many "
                "appear. Therefore, it's left as unimplemented for now."
            )
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        self.data_range = DataRange.safe(data_range)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.BNode:
        """Represent the data values existential quantification for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        p_o = _get_data_value_po(graph, converter, self.data_property_expressions)
        graph.add((node, self.property_type, self.data_range.to_rdflib_node(graph, converter)))
        graph.add((node, *p_o))
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the existential quantification."""
        return list_to_funowl((*self.data_property_expressions, self.data_range))


def _get_data_value_po(
    graph, converter, dpes: Sequence[DataPropertyExpression]
) -> tuple[term.URIRef, term.IdentifiedNode]:
    if len(dpes) >= 2:
        # Note that this is currently not possible to get to with
        return OWL.onProperties, _make_sequence(graph, dpes, converter=converter)
    else:
        return OWL.onProperty, dpes[0].to_rdflib_node(graph, converter)


class DataSomeValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.1 Existential Qualifications <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2>`_."""

    property_type: ClassVar[term.URIRef] = OWL.someValuesFrom


class DataAllValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.2 Universal Qualifications <https://www.w3.org/TR/owl2-syntax/#Universal_Quantification_2>`_."""

    property_type: ClassVar[term.URIRef] = OWL.allValuesFrom


class DataHasValue(_DataValuesFrom):
    """A class expression defined in `8.4.3 Literal Value Restriction <https://www.w3.org/TR/owl2-syntax/#Literal_Value_Restriction>`_."""

    property_type: ClassVar[term.URIRef] = OWL.hasValue
    data_property_expression: DataPropertyExpression
    literal: LiteralBox

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        literal: LiteralBoxOrHint,
    ) -> None:
        """Instantiate a literal value restriction."""
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.literal = LiteralBox(literal)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.BNode:
        """Represent this literal value restriction for RDF."""
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        graph.add((node, OWL.hasValue, self.literal.to_rdflib_node(graph, converter)))
        graph.add(
            (node, OWL.onProperty, self.data_property_expression.to_rdflib_node(graph, converter))
        )
        return node

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the literal value restriction."""
        return f"{self.data_property_expression.to_funowl()} {self.literal.to_funowl()}"


class _DataCardinality(_Cardinality):
    """A grouping class for data cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    property_type: ClassVar[term.URIRef] = OWL.onDataRange
    property_expression_type: ClassVar[term.URIRef] = OWL.DatatypeProperty
    property_expression: DataPropertyExpression
    target_expression: DataRange | None

    def __init__(
        self,
        cardinality: int,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        data_range: DataRange | IdentifierBoxOrHint | None = None,
    ) -> None:
        """Instantiate a data cardinality restriction."""
        super().__init__(
            cardinality,
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


class Axiom(Box):
    """A model for an `axiom <https://www.w3.org/TR/owl2-syntax/#Axioms>`_."""

    annotations: list[Annotation]

    def __init__(self, annotations: list[Annotation] | None = None) -> None:
        """Instantiate an axiom, with an optional list of annotations."""
        self.annotations = annotations or []

    def to_funowl_args(self) -> str:
        """Get the functional OWL tag representing the axiom."""
        if self.annotations:
            return list_to_funowl(self.annotations) + " " + self._funowl_inside_2()
        return self._funowl_inside_2()

    @abstractmethod
    def _funowl_inside_2(self) -> str:
        """Get the inside of the functional OWL tag representing the axiom."""


class ClassAxiom(Axiom):
    """A model for a class axiom."""


def _add_triple(
    graph: Graph,
    s: term.IdentifiedNode,
    p: term.IdentifiedNode,
    o: term.IdentifiedNode | term.Literal,
    annotations: Annotations | None = None,
    *,
    converter: Converter,
) -> term.BNode:
    graph.add((s, p, o))
    return _add_triple_annotations(graph, s, p, o, annotations=annotations, converter=converter)


def _add_triple_annotations(
    graph: Graph,
    s: term.IdentifiedNode,
    p: term.IdentifiedNode,
    o: term.IdentifiedNode | term.Literal,
    *,
    annotations: Annotations | None = None,
    type: term.URIRef | None = None,
    converter: Converter,
    force_for_negative_assertion: bool = False,
    reified_s=OWL.annotatedSource,
    reified_p=OWL.annotatedProperty,
    reified_o=OWL.annotatedTarget,
) -> term.BNode:
    # in order to represent annotations on a triple,
    # we need to "reify" the triple, which means to
    # represent it with a blank node
    reified_triple = term.BNode()
    if not annotations and not force_for_negative_assertion:
        return reified_triple
    if type is None:
        type = OWL.Axiom
    graph.add((reified_triple, RDF.type, type))
    graph.add((reified_triple, reified_s, s))
    graph.add((reified_triple, reified_p, p))
    graph.add((reified_triple, reified_o, o))
    for annotation in annotations or []:
        annotation._add_to_triple(graph, reified_triple, converter)
    return reified_triple


class SubClassOf(ClassAxiom):
    r"""A class axiom defined in `9.1.1 "Subclass Axioms" <https://www.w3.org/TR/owl2-syntax/#Subclass_Axioms>`_.

    Example:
    >>> SubClassOf("a:Baby", "a:Child")  # Each baby is a child.
    >>> SubClassOf("a:Child", "a:Person")  # Each child is a person.
    >>> ClassAssertion("a:Baby", "a:Stewie")  # Stewie is a baby.

    This axiom can be applied to more complicated expressions. For example,
    here's the long form for a :class:`FunctionalDataProperty`:

    >>> axiom = SubClassOf("owl:Thing", DataMaxCardinality(1, "a:hasAge"))

    which itself is eqivalent to:

    >>> FunctionalDataProperty("a:hasAge")
    """

    child: ClassExpression
    parent: ClassExpression

    def __init__(
        self,
        child: ClassExpression | IdentifierBoxOrHint,
        parent: ClassExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a subclass axiom."""
        self.child = ClassExpression.safe(child)
        self.parent = ClassExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the subclass axiom for RDF."""
        s = self.child.to_rdflib_node(graph, converter)
        o = self.parent.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, RDFS.subClassOf, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class EquivalentClasses(ClassAxiom):
    """A class axiom defined in `9.1.2 "Subclass Axioms" <https://www.w3.org/TR/owl2-syntax/#Equivalent_Classes>`_.

    >>> EquivalentClasses(
    ...     [
    ...         "a:GriffinFamilyMember",
    ...         ObjectOneOf(["a:Peter", "a:Lois", "a:Stewie", "a:Meg", "a:Chris", "a:Brian"]),
    ...     ]
    ... )
    """

    class_expression: Sequence[ClassExpression]

    def __init__(
        self,
        class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a equivalent class axiom."""
        if len(class_expressions) < 2:
            raise ValueError
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the equivalent class axiom for RDF."""
        rv = term.BNode()
        nodes = [ce.to_rdflib_node(graph, converter) for ce in self.class_expressions]
        for s, o in itt.pairwise(nodes):
            _add_triple(graph, s, OWL.equivalentClass, o, self.annotations, converter=converter)
        # TODO connect all triples to this BNode?
        return rv

    def _funowl_inside_2(self) -> str:
        return list_to_funowl(self.class_expressions)


class DisjointClasses(ClassAxiom):
    """A class axiom defined in `9.1.3 "Disjoint Classes" <https://www.w3.org/TR/owl2-syntax/#Disjoint_Classes>`_.

    >>> DisjointClasses("a:Boy a:Girl".split())
    """

    class_expression: Sequence[ClassExpression]

    def __init__(
        self,
        class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a disjoint classes axiom."""
        if len(class_expressions) < 2:
            raise ValueError
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the disjoint classes axiom for RDF."""
        nodes = [ce.to_rdflib_node(graph, converter) for ce in self.class_expressions]
        if len(nodes) == 2:
            return _add_triple(
                graph, nodes[0], OWL.disjointWith, nodes[1], self.annotations, converter=converter
            )
        else:
            node = term.BNode()
            graph.add((node, RDF.type, OWL.AllDisjointClasses))
            _add_triple(
                graph,
                node,
                OWL.members,
                _make_sequence_nodes(graph, nodes),
                self.annotations,
                converter=converter,
            )
            return node

    def _funowl_inside_2(self) -> str:
        return list_to_funowl(self.class_expressions)


class DisjointUnion(ClassAxiom):
    """A class axiom defined in `9.1.4 "Disjoint Union of Class Expressions" <https://www.w3.org/TR/owl2-syntax/#Disjoint_Union_of_Class_Expressions>`_."""

    parent: SimpleClassExpression
    class_expression: Sequence[ClassExpression]

    def __init__(
        self,
        parent: IdentifierBoxOrHint,
        class_expressions: Sequence[ClassExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a disjoint union of class expressions axiom."""
        if len(class_expressions) < 2:
            raise ValueError
        self.parent = SimpleClassExpression(parent)
        self.class_expressions = [ClassExpression.safe(ce) for ce in class_expressions]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the disjoint union of class expressions axiom as RDF."""
        return _add_triple(
            graph,
            self.parent.to_rdflib_node(graph, converter),
            OWL.disjointUnionOf,
            _make_sequence(graph, self.class_expressions, converter),
            self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        return list_to_funowl((self.parent, *self.class_expressions))


"""Section 9.2: Object Property Axioms"""


class ObjectPropertyAxiom(Axiom):
    """A grouping class for `9.2 "Object Property Axioms" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Axioms>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/A_objectproperty2.gif
    """


class ObjectPropertyChain(Box):
    """Represents a list of object properties."""

    object_property_expressions: Sequence[ObjectPropertyExpression]

    def __init__(
        self, object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierBoxOrHint]
    ):
        """Instantiate a list of object property expressions."""
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the list of object property expressions for RDF."""
        nodes = [ope.to_rdflib_node(graph, converter) for ope in self.object_property_expressions]
        return _make_sequence_nodes(graph, nodes)

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the object property chain."""
        return list_to_funowl(self.object_property_expressions)


SubObjectPropertyExpression: TypeAlias = ObjectPropertyExpression | ObjectPropertyChain


class SubObjectPropertyOf(ObjectPropertyAxiom):  # 9.2.1
    """An object property axiom defined in `9.2.1 "Object Subproperties" <https://www.w3.org/TR/owl2-syntax/#Object_Subproperties>`_."""

    child: SubObjectPropertyExpression
    parent: ObjectPropertyExpression

    def __init__(
        self,
        child: SubObjectPropertyExpression | IdentifierBoxOrHint,
        parent: ObjectPropertyExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate an object subproperty axiom."""
        if isinstance(child, ObjectPropertyChain):
            self.child = child
        else:
            self.child = ObjectPropertyExpression.safe(child)
        self.parent = ObjectPropertyExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the object subproperty axiom for RDF."""
        s = self.child.to_rdflib_node(graph, converter)
        o = self.parent.to_rdflib_node(graph, converter)
        if isinstance(self.child, ObjectInverseOf):
            self.child.declare_wrapped_ope(graph, converter)
        if isinstance(self.parent, ObjectInverseOf):
            self.parent.declare_wrapped_ope(graph, converter)
        if isinstance(self.child, ObjectPropertyChain):
            return _add_triple(
                graph, o, OWL.propertyChainAxiom, s, self.annotations, converter=converter
            )
        else:
            return _add_triple(
                graph, s, RDFS.subPropertyOf, o, self.annotations, converter=converter
            )

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class _ObjectPropertyList(ObjectPropertyAxiom):
    """A model for an object property axiom that accepts a list of object property expressions."""

    object_property_expressions: Sequence[ObjectPropertyExpression]

    def __init__(
        self,
        object_property_expressions: Sequence[ObjectPropertyExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instntiate an object property list."""
        if len(object_property_expressions) < 2:
            raise ValueError
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return list_to_funowl(self.object_property_expressions)


def _equivalent_xxx(
    graph: Graph,
    expressions: Iterable[Box],
    *,
    annotations: Annotations | None = None,
    converter: Converter,
) -> term.BNode:
    nodes = [expression.to_rdflib_node(graph, converter) for expression in expressions]
    for s, o in itt.combinations(nodes, 2):
        _add_triple(graph, s, OWL.equivalentProperty, o, annotations, converter=converter)
    # an unused blank node is returned here, since adding
    # these relationship doesn't correspond to a node itself
    return term.BNode()


class EquivalentObjectProperties(_ObjectPropertyList):
    """An object property axiom defined in `9.2.2 "Equivalent Object Subproperties" <https://www.w3.org/TR/owl2-syntax/#Equivalent_Object_Properties>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the equivalent object subproperties axiom for RDF."""
        return _equivalent_xxx(
            graph,
            self.object_property_expressions,
            annotations=self.annotations,
            converter=converter,
        )


def _disjoint_xxx(
    graph: Graph,
    expressions: Iterable[Box],
    *,
    annotations: Annotations | None = None,
    converter: Converter,
) -> term.BNode:
    nodes = [expression.to_rdflib_node(graph, converter) for expression in expressions]
    nodes = sorted(nodes, key=str)
    if len(nodes) == 2:
        return _add_triple(
            graph, nodes[0], OWL.propertyDisjointWith, nodes[1], annotations, converter=converter
        )
    else:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.AllDisjointProperties))
        _add_triple(
            graph,
            node,
            OWL.members,
            _make_sequence_nodes(graph, nodes),
            annotations,
            converter=converter,
        )
        return node


class DisjointObjectProperties(_ObjectPropertyList):  # 9.2.3
    """An object property axiom defined in `9.2.3 "Disjoint Object Properties" <https://www.w3.org/TR/owl2-syntax/#Disjoint_Object_Properties>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the disjoint object properties axiom for RDF."""
        return _disjoint_xxx(
            graph,
            self.object_property_expressions,
            annotations=self.annotations,
            converter=converter,
        )


class InverseObjectProperties(ObjectPropertyAxiom):  # 9.2.4
    """An object property axiom defined in `9.2.4 "Inverse Object Properties" <https://www.w3.org/TR/owl2-syntax/#Inverse_Object_Properties_2>`_.

    For example, having a father is the opposite of being a father of someone:

    >>> InverseObjectProperties("a:hasFather", "a:fatherOf")
    """

    left: ObjectPropertyExpression
    right: ObjectPropertyExpression

    def __init__(
        self,
        left: ObjectPropertyExpression | IdentifierBoxOrHint,
        right: ObjectPropertyExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize an inverse object property axiom."""
        self.left = ObjectPropertyExpression.safe(left)
        self.right = ObjectPropertyExpression.safe(right)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the inverse object property axiom for RDF."""
        # note these are backwards, since everything is backwards in OFN :shrug:
        s = self.right.to_rdflib_node(graph, converter)
        o = self.left.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, OWL.inverseOf, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.left.to_funowl()} {self.right.to_funowl()}"


class _ObjectPropertyTyping(ObjectPropertyAxiom):  # 9.2.4
    """An object property axiom for a range or domain."""

    property_type: ClassVar[term.URIRef]
    object_property_expression: ObjectPropertyExpression
    value: ClassExpression

    def __init__(
        self,
        left: ObjectPropertyExpression | IdentifierBoxOrHint,
        right: ClassExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a object property domain or range."""
        self.object_property_expression = ObjectPropertyExpression.safe(left)
        self.value = ClassExpression.safe(right)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the object property domain or range for RDF."""
        s = self.object_property_expression.to_rdflib_node(graph, converter)
        o = self.value.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, self.property_type, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.value.to_funowl()}"


class ObjectPropertyDomain(_ObjectPropertyTyping):  # 9.2.5
    """An object property axiom defined in `9.2.5 "Object Property Domain" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Domain>`_.

    Consider the ontology consisting of the following axioms.

    >>> ObjectPropertyDomain("a:hasDog", "a:Person")  # Only people can own dogs.
    >>> ObjectPropertyAssertion("a:hasDog", "a:Peter", "a:Brian")  # Brian is a dog of Peter.

    This ontology therefore entails:

    >>> ClassAssertion("a:Person", "a:Peter")  # Peter is a person
    """

    property_type: ClassVar[term.URIRef] = RDFS.domain


class ObjectPropertyRange(_ObjectPropertyTyping):  # 9.2.6
    """An object property axiom defined in `9.2.5 "Object Property Range" <https://www.w3.org/TR/owl2-syntax/#Object_Property_Range>`_.

    Consider the ontology consisting of the following axioms.

    >>> # The range of the a:hasDog property is the class a:Dog.
    >>> ObjectPropertyRange("a:hasDog", "a:Dog")
    >>> ObjectPropertyAssertion("a:hasDog", "a:Peter", "a:Brian")  # Brian is a dog of Peter.

    By the first axiom, each individual that has an incoming
    ``a:hasDog`` connection must be an instance of ``a:Dog``.
    Therefore, ``a:Brian`` can be classified as an instance of
    ``a:Dog``; that is, this ontology entails the following assertion:

    >>> ClassAssertion("a:Dog", "a:Brian")
    """

    property_type: ClassVar[term.URIRef] = RDFS.range


class _UnaryObjectProperty(ObjectPropertyAxiom):
    """A grouping class for object property axioms with a single argument."""

    property_type: ClassVar[term.URIRef]
    object_property_expression: ObjectPropertyExpression

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a unary object property axiom."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the unary object property axiom for RDF."""
        return _add_triple(
            graph,
            self.object_property_expression.to_rdflib_node(graph, converter),
            RDF.type,
            self.property_type,
            self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        return self.object_property_expression.to_funowl()


class FunctionalObjectProperty(_UnaryObjectProperty):  # 9.2.7
    """An object property axiom defined in `9.2.7 "Functional Object Properties" <https://www.w3.org/TR/owl2-syntax/#Functional_Object_Properties>`_.

    Consider the ontology consisting of the following axioms.

    >>> FunctionalObjectProperty("a:hasFather")  # Each object can have at most one father.
    >>> ObjectPropertyAssertion("a:hasFather", "a:Stewie", "a:Peter")  # Peter is Stewie's father.
    >>> ObjectPropertyAssertion(
    ...     "a:hasFather", "a:Stewie", "a:Peter_Griffin"
    ... )  # Peter Griffin is Stewie's father.

    By the first axiom, ``a:hasFather`` can point from a:Stewie to
    at most one distinct individual, so ``a:Peter`` and ``a:Peter_Griffin``
    must be equal; that is, this ontology entails the following assertion:

    >>> SameIndividual(["a:Peter", "a:Peter_Griffin"])

    One might expect the previous ontology to be inconsistent, since
    the a:hasFather property points to two different values for
    ``a:Stewie``. OWL 2, however, does not make the unique name assumption,
    so ``a:Peter`` and ``a:Peter_Griffin`` are not necessarily distinct individuals.
    If the ontology were extended with the following assertion, then it
    would indeed become inconsistent:

    >>> DifferentIndividuals(["a:Peter", "a:Peter_Griffin"])
    """

    property_type = OWL.FunctionalProperty


class InverseFunctionalObjectProperty(_UnaryObjectProperty):
    """An object property axiom defined in `9.2.8 "Inverse-Functional Object Properties" <https://www.w3.org/TR/owl2-syntax/#Inverse-Functional_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.InverseFunctionalProperty


class ReflexiveObjectProperty(_UnaryObjectProperty):
    """An object property axiom defined in `9.2.9 "Irreflexive Object Properties" <https://www.w3.org/TR/owl2-syntax/#Reflexive_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.ReflexiveProperty


class IrreflexiveObjectProperty(_UnaryObjectProperty):
    """An object property axiom defined in `9.2.10 "Reflexive Object Properties" <https://www.w3.org/TR/owl2-syntax/#Ireflexive_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.IrreflexiveProperty


class SymmetricObjectProperty(_UnaryObjectProperty):
    """An object property axiom defined in `9.2.11 "Symmetric Object Properties" <https://www.w3.org/TR/owl2-syntax/#Symmetric_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.SymmetricProperty


class AsymmetricObjectProperty(_UnaryObjectProperty):  # 9.2.12
    """An object property axiom defined in `9.2.12 "Asymmetric Object Properties" <https://www.w3.org/TR/owl2-syntax/#Asymmetric_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.AsymmetricProperty


class TransitiveObjectProperty(_UnaryObjectProperty):  # 9.2.13
    """An object property axiom defined in `9.2.13 "Transitive Object Properties" <https://www.w3.org/TR/owl2-syntax/#Transitive_Object_Properties>`_."""

    property_type: ClassVar[term.URIRef] = OWL.TransitiveProperty


"""9.3: Data Property Axioms"""


class DataPropertyAxiom(Axiom):
    """A model for `9.3 "Data Property Axioms" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Axioms>`_."""


class SubDataPropertyOf(DataPropertyAxiom):
    """A data property axiom for `9.3.1 "Data Subproperties" <https://www.w3.org/TR/owl2-syntax/#Data_Subproperties>`_."""

    child: DataPropertyExpression
    parent: DataPropertyExpression

    def __init__(
        self,
        child: DataPropertyExpression | IdentifierBoxOrHint,
        parent: DataPropertyExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a data subproperties axiom."""
        self.child = DataPropertyExpression.safe(child)
        self.parent = DataPropertyExpression.safe(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the data subproperties axiom for RDF."""
        s = self.child.to_rdflib_node(graph, converter)
        o = self.parent.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class _DataPropertyList(DataPropertyAxiom):
    """A model for a data property axiom that takes a list of data property expressions."""

    data_property_expressions: Sequence[DataPropertyExpression]

    def __init__(
        self,
        data_property_expressions: Sequence[DataPropertyExpression | IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a data property list axiom."""
        if len(data_property_expressions) < 2:
            raise ValueError
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return list_to_funowl(self.data_property_expressions)


class EquivalentDataProperties(_DataPropertyList):
    """A data property axiom for `9.3.2 "Equivalent Data Properties" <https://www.w3.org/TR/owl2-syntax/#Equivalent_Data_Properties>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the equivalent data properties axiom for RDF."""
        for dpe in self.data_property_expressions:
            graph.add((dpe.to_rdflib_node(graph, converter), RDF.type, OWL.DatatypeProperty))
        return _equivalent_xxx(
            graph,
            self.data_property_expressions,
            annotations=self.annotations,
            converter=converter,
        )


class DisjointDataProperties(_DataPropertyList):
    """A data property axiom for `9.3.3 "Disjoint Data Properties" <https://www.w3.org/TR/owl2-syntax/#Disjoint_Data_Properties>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the disjoint data properties axiom for RDF."""
        for dpe in self.data_property_expressions:
            graph.add((dpe.to_rdflib_node(graph, converter), RDF.type, OWL.DatatypeProperty))
        return _disjoint_xxx(
            graph, self.data_property_expressions, annotations=self.annotations, converter=converter
        )


class _DataPropertyTyping(DataPropertyAxiom):  # 9.2.4
    """An axiom that represents the range or domain of a data property."""

    property_type: ClassVar[term.URIRef]
    data_property_expression: DataPropertyExpression
    target: Box

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the equivalent data properties axiom for RDF."""
        s = self.data_property_expression.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.DatatypeProperty))
        o = self.target.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, self.property_type, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.data_property_expression.to_funowl()} {self.target.to_funowl()}"


class DataPropertyDomain(_DataPropertyTyping):  # 9.3.4
    """A data property axiom for `9.3.4 "Data Property Domain" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Domain>`_."""

    property_type: ClassVar[term.URIRef] = RDFS.domain

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        class_expression: ClassExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a data property domain axiom."""
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.target = ClassExpression.safe(class_expression)
        super().__init__(annotations)


class DataPropertyRange(_DataPropertyTyping):
    """A data property axiom for `9.3.5 "Data Property Range" <https://www.w3.org/TR/owl2-syntax/#Data_Property_Range>`_."""

    property_type: ClassVar[term.URIRef] = RDFS.range

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        data_range: DataRange | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a data property range axiom."""
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.target = DataRange.safe(data_range)
        super().__init__(annotations)


class FunctionalDataProperty(DataPropertyAxiom):
    """A data property axiom for `9.3.6 "Functional Data Properties" <https://www.w3.org/TR/owl2-syntax/#Functional_Data_Properties>`_.

    Consider the ontology consisting of the following axioms.

    >>> FunctionalDataProperty("a:hasAge")  # Each object can have at most one age.
    >>> DataPropertyAssertion("a:hasAge", "a:Meg", 17)  # Meg is seventeen years old.

    By the first axiom, ``a:hasAge`` can point from ``a:Meg`` to at most one
    distinct literal. In this example ontology, this axiom is satisfied. If,
    however, the ontology were extended with the following assertion, the
    semantics of functionality axioms would imply that ``"15"^^xsd:integer`` is
    equal to ``"17"^^xsd:integer``, which is a contradiction and the ontology
    would become inconsistent:

    >>> DataPropertyAssertion("a:hasAge", "a:Meg", 15)
    """

    data_property_expression: DataPropertyExpression

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ):
        """Instantiate a functional data property axiom."""
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the functional data property for RDF."""
        return _add_triple(
            graph,
            self.data_property_expression.to_rdflib_node(graph, converter),
            RDF.type,
            OWL.FunctionalProperty,
            self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        return self.data_property_expression.to_funowl()


"""Section 9.4: Datatype Definitions"""


class DatatypeDefinition(Axiom):
    """A model for `9.4 "Datatype Definitions" <https://www.w3.org/TR/owl2-syntax/#Datatype_Definitions>`_."""

    datatype: IdentifierBox
    data_range: DataRange

    def __init__(
        self,
        datatype: IdentifierBoxOrHint,
        data_range: DataRange | IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a datatype definition axiom."""
        self.datatype = IdentifierBox(datatype)
        self.data_range = DataRange.safe(data_range)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the datatype definition axiom for RDF."""
        s = self.datatype.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, RDFS.Datatype))
        return _add_triple(
            graph,
            s,
            OWL.equivalentClass,
            self.data_range.to_rdflib_node(graph, converter),
            annotations=self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        return f"{self.datatype.to_funowl()} {self.data_range.to_funowl()}"


"""Section 9.5: Keys"""


class HasKey(Axiom):
    """An axiom for `9.5 "Keys" <https://www.w3.org/TR/owl2-syntax/#Keys>`_."""

    class_expression: ClassExpression
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
        """Instantiate a "has key" axiom."""
        self.class_expression = ClassExpression.safe(class_expression)
        self.object_property_expressions = [
            ObjectPropertyExpression.safe(ope) for ope in object_property_expressions
        ]
        self.data_property_expressions = [
            DataPropertyExpression.safe(dpe) for dpe in data_property_expressions
        ]
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the "has key" axiom for RDF."""
        object_and_data_property_expressions: list[
            ObjectPropertyExpression | DataPropertyExpression
        ] = []
        object_and_data_property_expressions.extend(self.object_property_expressions)
        object_and_data_property_expressions.extend(self.data_property_expressions)

        return _add_triple(
            graph,
            self.class_expression.to_rdflib_node(graph, converter),
            OWL.hasKey,
            _make_sequence(graph, object_and_data_property_expressions, converter),
            annotations=self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        aa = f"{self.class_expression.to_funowl()}"
        if self.object_property_expressions:
            aa += f" ( {list_to_funowl(self.object_property_expressions)} )"
        else:
            aa += " ()"
        if self.data_property_expressions:
            aa += f" ( {list_to_funowl(self.data_property_expressions)} )"
        else:
            aa += " ()"
        return aa


"""Section 9.6: Assertions"""


class Assertion(Axiom):
    """Axioms for `9.6 "Assertions" <https://www.w3.org/TR/owl2-syntax/#Assertions>`_."""


class _IndividualListAssertion(Assertion):
    """A grouping class for individual equality and inequality axioms."""

    individuals: Sequence[IdentifierBox]

    def __init__(
        self,
        individuals: Sequence[IdentifierBoxOrHint],
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate an individual list axiom."""
        self.individuals = [IdentifierBox(i) for i in individuals]
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return list_to_funowl(self.individuals)


class SameIndividual(_IndividualListAssertion):
    """An axiom for `9.6.1 "Individual Equality" <https://www.w3.org/TR/owl2-syntax/#Individual_Equality>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the individual equality axiom for RDF."""
        nodes = [i.to_rdflib_node(graph, converter) for i in self.individuals]
        for node in nodes:
            graph.add((node, RDF.type, OWL.NamedIndividual))
        for s, o in itt.combinations(nodes, 2):
            _add_triple(graph, s, OWL.sameAs, o, annotations=self.annotations, converter=converter)
        # TODO connect this node to triples?
        return term.BNode()


class DifferentIndividuals(_IndividualListAssertion):
    """An axiom for `9.6.2 "Individual Inequality" <https://www.w3.org/TR/owl2-syntax/#Individual_Inequality>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the individual inequality axiom for RDF."""
        nodes = [i.to_rdflib_node(graph, converter) for i in self.individuals]
        for node in nodes:
            graph.add((node, RDF.type, OWL.NamedIndividual))
        if len(nodes) == 2:
            return _add_triple(
                graph,
                nodes[0],
                OWL.differentFrom,
                nodes[1],
                annotations=self.annotations,
                converter=converter,
            )
        else:
            node = term.BNode()
            graph.add((node, RDF.type, OWL.AllDifferent))
            graph.add((node, OWL.distinctMembers, _make_sequence_nodes(graph, nodes)))
            # FIXME add annotations
            return node


class ClassAssertion(Assertion):
    """An axiom for `9.6.3 "Class Assertions" <https://www.w3.org/TR/owl2-syntax/#Class_Assertions>`_."""

    class_expression: ClassExpression
    individual: IdentifierBox

    def __init__(
        self,
        class_expression: ClassExpression | IdentifierBoxOrHint,
        individual: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Instantiate a class assertion axiom."""
        self.class_expression = ClassExpression.safe(class_expression)
        self.individual = IdentifierBox(individual)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the class assertion axiom for RDF."""
        s = self.individual.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.NamedIndividual))
        return _add_triple(
            graph,
            s,
            RDF.type,
            self.class_expression.to_rdflib_node(graph, converter),
            annotations=self.annotations,
            converter=converter,
        )

    def _funowl_inside_2(self) -> str:
        return f"{self.class_expression.to_funowl()} {self.individual.to_funowl()}"


class _BaseObjectPropertyAssertion(Assertion):
    """A grouping class for positive and negative object property assertion axioms."""

    object_property_expression: ObjectPropertyExpression
    source_individual: IdentifierBox
    target_individual: IdentifierBox

    def __init__(
        self,
        object_property_expression: ObjectPropertyExpression | IdentifierBoxOrHint,
        source_individual: IdentifierBoxOrHint,
        target_individual: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize an object property assertion axiom."""
        self.object_property_expression = ObjectPropertyExpression.safe(object_property_expression)
        self.source_individual = IdentifierBox(source_individual)
        self.target_individual = IdentifierBox(target_individual)
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.object_property_expression.to_funowl()} {self.source_individual.to_funowl()} {self.target_individual.to_funowl()}"


class ObjectPropertyAssertion(_BaseObjectPropertyAssertion):
    """An axiom for `9.6.4 "Positive Object Property Assertions" <https://www.w3.org/TR/owl2-syntax/#Positive_Object_Property_Assertions>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the positive object property assertion axiom for RDF."""
        s = self.source_individual.to_rdflib_node(graph, converter)
        o = self.target_individual.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.NamedIndividual))
        graph.add((o, RDF.type, OWL.NamedIndividual))
        if isinstance(self.object_property_expression, ObjectInverseOf):
            # flip them around
            s, o = o, s
            # unpack the inverse property
            p = self.object_property_expression.object_property.to_rdflib_node(graph, converter)
            # make sure the inverse property is declared
            graph.add((p, RDF.type, OWL.ObjectProperty))
        else:
            p = self.object_property_expression.to_rdflib_node(graph, converter)

        return _add_triple(graph, s, p, o, annotations=self.annotations, converter=converter)


class NegativeObjectPropertyAssertion(_BaseObjectPropertyAssertion):
    """An axiom for `9.6.5 "Negative Object Property Assertions" <https://www.w3.org/TR/owl2-syntax/#Negative_Object_Property_Assertions>`_."""

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the negative object property assertion axiom for RDF."""
        s = self.source_individual.to_rdflib_node(graph, converter)
        o = self.target_individual.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.NamedIndividual))
        graph.add((o, RDF.type, OWL.NamedIndividual))
        if isinstance(self.object_property_expression, ObjectInverseOf):
            # TODO OWLAPI is not consistent with the way ObjectPropertyAssertion and
            #  NegativeObjectPropertyAssertion work. For some reason, it doesn't
            #  flip the subject and object / unpack the inverse OPE for
            #  NegativeObjectPropertyAssertion. Therefore, it's implemented here
            #  to reflect that. Need to make an issue on OWLAPI about this
            self.object_property_expression.declare_wrapped_ope(graph, converter)
        return _add_triple_annotations(
            graph,
            s,
            self.object_property_expression.to_rdflib_node(graph, converter),
            o,
            annotations=self.annotations,
            type=OWL.NegativePropertyAssertion,
            converter=converter,
            force_for_negative_assertion=True,
            reified_p=OWL.assertionProperty,
            reified_s=OWL.sourceIndividual,
            reified_o=OWL.targetIndividual,
        )


class _BaseDataPropertyAssertion(Assertion):
    """A grouping class for positive and negative data property assertion axioms."""

    source_individual: IdentifierBox
    target: PrimitiveBox

    def __init__(
        self,
        data_property_expression: DataPropertyExpression | IdentifierBoxOrHint,
        source_individual: IdentifierBoxOrHint,
        target: PrimitiveHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize a data property assertion axiom."""
        self.data_property_expression = DataPropertyExpression.safe(data_property_expression)
        self.source_individual = IdentifierBox(source_individual)
        self.target = _safe_primitive_box(target)
        super().__init__(annotations)

    def _funowl_inside_2(self) -> str:
        return f"{self.data_property_expression.to_funowl()} {self.source_individual.to_funowl()} {self.target.to_funowl()}"


class DataPropertyAssertion(_BaseDataPropertyAssertion):
    """An axiom for `9.6.6 "Positive Data Property Assertions" <https://www.w3.org/TR/owl2-syntax/#Positive_Data_Property_Assertions>`_.

    >>> DataPropertyAssertion("a:hasAge", "a:Meg", 17)
    """

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the positive data property assertion axiom for RDF."""
        s = self.source_individual.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.NamedIndividual))
        return _add_triple(
            graph,
            s,
            self.data_property_expression.to_rdflib_node(graph, converter),
            self.target.to_rdflib_node(graph, converter),
            annotations=self.annotations,
            converter=converter,
        )


class NegativeDataPropertyAssertion(_BaseDataPropertyAssertion):
    """An axiom for `9.6.7 "Negative Data Property Assertions" <https://www.w3.org/TR/owl2-syntax/#Negative_Data_Property_Assertions>`_.

    >>> NegativeDataPropertyAssertion("a:hasAge", "a:Meg", 5)
    """

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the negative data property assertion axiom for RDF."""
        s = self.source_individual.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.NamedIndividual))
        return _add_triple_annotations(
            graph,
            s,
            self.data_property_expression.to_rdflib_node(graph, converter),
            self.target.to_rdflib_node(graph, converter),
            annotations=self.annotations,
            type=OWL.NegativePropertyAssertion,
            converter=converter,
            force_for_negative_assertion=True,
            reified_p=OWL.assertionProperty,
            reified_s=OWL.sourceIndividual,
            reified_o=OWL.targetValue,
        )


"""Section 10: Annotations"""


class Annotation(Box):  # 10.1
    """An element defined in `10.1 "Annotations of Ontologies, Axioms, and other Annotations" <https://www.w3.org/TR/owl2-syntax/#Annotations_of_Ontologies.2C_Axioms.2C_and_other_Annotations>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/Annotations.gif

    Annotations can be used to add additional context, like curation provenance, to
    assertions

    >>> AnnotationAssertion(
    ...     "skos:exactMatch",
    ...     "agrovoc:0619dd9e",
    ...     "agro:00000137",
    ...     annotations=[
    ...         Annotation("dcterms:contributor", "orcid:0000-0003-4423-4370"),
    ...         Annotation("sssom:mapping_justification", "semapv:ManualMappingCuration"),
    ...     ],
    ... )

    Annotations can even be used on themselves, adding arbitrary levels of detail.
    In the following example, we annotate the affiliation of the contributor
    via the `wd:P1416 (affiliation) <https://www.wikidata.org/wiki/Property:P1416>`_
    predicate.

    >>> AnnotationAssertion(
    ...     "skos:exactMatch",
    ...     "agrovoc:0619dd9e",
    ...     "agro:00000137",
    ...     annotations=[
    ...         Annotation(
    ...             "dcterms:contributor",
    ...             "orcid:0000-0003-4423-4370",
    ...             annotations=[
    ...                 Annotation("wd:P1416", "wd:Q126066280"),
    ...             ],
    ...         ),
    ...         Annotation("sssom:mapping_justification", "semapv:ManualMappingCuration"),
    ...     ],
    ... )
    """

    annotation_property: IdentifierBox
    value: PrimitiveBox
    annotations: list[Annotation]

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: list[Annotation] | None = None,
    ) -> None:
        """Initialize an annotation."""
        self.annotation_property = IdentifierBox(annotation_property)
        self.value = _safe_primitive_box(value)
        self.annotations = annotations or []

    def to_rdflib_node(
        self, graph: Graph, converter: Converter
    ) -> term.IdentifiedNode:  # pragma: no cover
        """Represent the annotation as an RDF node (unused)."""
        raise RuntimeError

    def _add_to_triple(
        self,
        graph: Graph,
        subject: term.IdentifiedNode,
        converter: Converter,
    ) -> None:
        annotation_property = self.annotation_property.to_rdflib_node(graph, converter)
        annotation_object = self.value.to_rdflib_node(graph, converter)
        graph.add((annotation_property, RDF.type, OWL.AnnotationProperty))
        graph.add((subject, annotation_property, annotation_object))
        if self.annotations:
            _add_triple_annotations(
                graph,
                subject,
                annotation_property,
                annotation_object,
                converter=converter,
                annotations=self.annotations,
                type=OWL.Annotation,
            )

    def to_funowl_args(self) -> str:
        """Get the inside of the functional OWL tag representing the annotation."""
        end = f"{self.annotation_property.to_funowl()} {self.value.to_funowl()}"
        if self.annotations:
            return list_to_funowl(self.annotations) + " " + end
        return end


Annotations: TypeAlias = list[Annotation]


class AnnotationAxiom(Axiom):  # 10.2
    """A grouping class for annotation axioms defined in `10.2 "Axiom Annotations" <https://www.w3.org/TR/owl2-syntax/#Annotation_Axioms>`_.

    .. image:: https://www.w3.org/TR/owl2-syntax/A_annotation.gif
    """


class AnnotationProperty(IdentifierBox):
    """A wrapper around an identifier box with custom functionality."""

    #: A set of built-in annotation properties that shouldn't be re-defined, since they
    #: appear in Table 3 of https://www.w3.org/TR/owl2-syntax/#IRIs.
    _SKIP: ClassVar[set[term.Node]] = {
        OWL.backwardCompatibleWith,
        OWL.deprecated,
        OWL.incompatibleWith,
        OWL.priorVersion,
        OWL.versionInfo,
        RDFS.comment,
        RDFS.isDefinedBy,
        RDFS.label,
        RDFS.seeAlso,
    }

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the annotation property for RDF."""
        node = super().to_rdflib_node(graph, converter)
        if node in self._SKIP:
            return node
        graph.add((node, RDF.type, OWL.AnnotationProperty))
        return node


class AnnotationAssertion(AnnotationAxiom):  # 10.2.1
    """An annotation axiom defined in `10.2.1 Annotation Assertion <https://www.w3.org/TR/owl2-syntax/#Annotation_Assertion>`_."""

    annotation_property: AnnotationProperty
    subject: IdentifierBox
    value: PrimitiveBox

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        subject: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: list[Annotation] | None = None,
    ) -> None:
        """Initialize an annotation assertion axiom."""
        self.annotation_property = AnnotationProperty(annotation_property)
        self.subject = IdentifierBox(subject)
        self.value = _safe_primitive_box(value)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the annotation assertion axiom for RDF."""
        return _add_triple(
            graph,
            self.subject.to_rdflib_node(graph, converter),
            self.annotation_property.to_rdflib_node(graph, converter),
            self.value.to_rdflib_node(graph, converter),
            annotations=self.annotations,
            converter=converter,
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

    child: AnnotationProperty
    parent: AnnotationProperty

    def __init__(
        self,
        child: IdentifierBoxOrHint,
        parent: IdentifierBoxOrHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize an annotation subproperty axiom."""
        self.child = AnnotationProperty(child)
        self.parent = AnnotationProperty(parent)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the annotation subproperty axiom for RDF."""
        s = self.child.to_rdflib_node(graph, converter)
        o = self.parent.to_rdflib_node(graph, converter)
        return _add_triple(graph, s, RDFS.subPropertyOf, o, self.annotations, converter=converter)

    def _funowl_inside_2(self) -> str:
        return f"{self.child.to_funowl()} {self.parent.to_funowl()}"


class AnnotationPropertyTypingAxiom(AnnotationAxiom):
    """A helper class that defines shared functionality between annotation property domains and ranges."""

    property_type: ClassVar[term.URIRef]
    annotation_property: AnnotationProperty
    value: PrimitiveBox

    def __init__(
        self,
        annotation_property: IdentifierBoxOrHint,
        value: PrimitiveHint,
        *,
        annotations: Annotations | None = None,
    ) -> None:
        """Initialize an annotation property range or domain axiom."""
        self.annotation_property = AnnotationProperty(annotation_property)
        self.value = _safe_primitive_box(value)
        super().__init__(annotations)

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Represent the annotation property range or domain axiom for RDF."""
        s = self.annotation_property.to_rdflib_node(graph, converter)
        o = self.value.to_rdflib_node(graph, converter)
        graph.add((s, RDF.type, OWL.AnnotationProperty))
        return _add_triple(graph, s, self.property_type, o, self.annotations, converter=converter)

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

    Using a string:

    >>> AnnotationPropertyRange("rdfs:label", "xsd:string")
    """

    property_type: ClassVar[term.URIRef] = RDFS.range
