"""A DSL for functional OWL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal, TypeAlias

import bioregistry
from curies import Reference
from rdflib import OWL, RDF, RDFS, XSD, Graph, collection, term

NNode: TypeAlias = term.URIRef | Reference


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


class SimpleNodeable(Nodeable):
    def __init__(self, nnode: NNode):
        self.nnode = nnode

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return _nnode_to_uriref(self.nnode)

    def to_funowl(self) -> str:
        return _nnode_to_funowl(self.nnode)

    def _funowl_inside(self) -> str:
        raise NotImplementedError


def make_sequence(graph: Graph, members: Sequence[Nodeable]) -> term.Node:
    """Make a sequence."""
    return make_sequence_nodes(graph, [m.to_rdflib_node(graph) for m in members])


def make_sequence_nodes(graph: Graph, members: Sequence[term.Node]) -> term.Node:
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


class Individual(Nodeable):
    """A model representing individuals."""


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
    pass


class InverseObjectProperty(ObjectPropertyExpression):
    def __init__(self, property: NNode):
        self.property = property

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        x = term.BNode()
        graph.add((x, OWL.inverseOf, _nnode_to_uriref(self.property)))
        return x

    def _funowl_inside(self) -> str:
        return _nnode_to_funowl(self.property)


class DataPropertyExpression(Nodeable):
    pass


"""
Section 7: Data Ranges
"""


class DataRange(Nodeable):
    pass


class SimpleDateRange(SimpleNodeable, DataRange):
    pass


class _ListDataRange(DataRange):
    def __init__(self, data_ranges: Sequence[DataRange]):
        self.data_ranges = data_ranges

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        raise NotImplementedError

    def _funowl_inside(self) -> str:
        return " ".join(f.to_funowl() for f in self.data_ranges)


class DataIntersectionOf(_ListDataRange):
    pass


class DataUnionOf(_ListDataRange):
    pass


class DataComplementOf(DataRange):
    def __init__(self, data_range: DataRange):
        self.data_range = data_range

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
        graph.add((node, OWL.oneOf, make_sequence_nodes(graph, self.literals)))
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


class _ObjectList(ClassExpression):
    """An abstract model for class expressions defined by lists.

    Defined in `8.1 Propositional Connectives and Enumeration of
    Individuals <Propositional_Connectives_and_Enumeration_of_Individuals>`_

    .. image:: https://www.w3.org/TR/owl2-syntax/C_propositional.gif
    """

    def __init__(self, nodes: Sequence[Nodeable], *, property: term.Node) -> None:
        """Initialize the model with a list of class expressions."""
        if len(nodes) < 2:
            raise ValueError("must have at least two class expressions")
        self.nodes = nodes
        self.property = property

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, self.property, make_sequence(graph, self.nodes)))
        return node

    def _funowl_inside(self) -> str:
        return " ".join(f.to_funowl() for f in self.nodes)


class ObjectIntersectionOf(_ObjectList):
    """A class expression defined in `8.1.1 Intersection of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Intersection_of_Class_Expressions>`_."""

    def __init__(self, nodes: Sequence[ClassExpression]) -> None:
        """Initialize the model with a list of class expressions."""
        super().__init__(nodes, property=OWL.intersectionOf)


class ObjectUnionOf(_ObjectList):
    """A class expression defined in `8.1.2 Union of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Union_of_Class_Expressions>`_."""

    def __init__(self, class_expressions: Sequence[ClassExpression]) -> None:
        """Initialize the model with a list of class expressions."""
        super().__init__(class_expressions, property=OWL.unionOf)


class ObjectComplementOf(ClassExpression):
    """A class expression defined in `8.1.3 Complement of Class Expressions <https://www.w3.org/TR/owl2-syntax/#Complement_of_Class_Expressions>`_."""

    def __init__(self, class_expression: ClassExpression) -> None:
        """Initialize the model with a single class expression."""
        self.class_expression = class_expression

    def to_rdflib_node(self, graph: Graph) -> term.Node:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Class))
        graph.add((node, OWL.complementOf, self.class_expression.to_rdflib_node(graph)))
        return node

    def _funowl_inside(self) -> str:
        return self.class_expression.to_funowl()


class ObjectOneOf(_ObjectList):
    """A class expression defined in `8.1.4 Enumeration of Individuals <https://www.w3.org/TR/owl2-syntax/#Enumeration_of_Individuals>`_."""

    def __init__(self, individuals: list[Individual]) -> None:
        """Initialize the model with a list of individuals."""
        super().__init__(individuals, property=OWL.oneOf)


class _Restriction(ClassExpression):
    def __init__(
        self,
        property_expression: Nodeable,
        object_expression: Nodeable,
        *,
        object_expression_predicate: term.Node,
    ) -> None:
        # TODO update type of property expression
        self.property_expression = property_expression
        self.object_expression = object_expression
        self.object_expression_predicate = object_expression_predicate

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        graph.add((node, OWL.onProperty, self.property_expression.to_rdflib_node(graph)))
        graph.add(
            (node, self.object_expression_predicate, self.object_expression.to_rdflib_node(graph))
        )
        return node

    def _funowl_inside(self) -> str:
        return f"{self.property_expression.to_funowl()} {self.object_expression.to_funowl()}"


class ObjectSomeValuesFrom(_Restriction):
    """A class expression defined in `8.2.1 Existential Quantification <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification>`_."""

    #
    def __init__(self, property_expression: Nodeable, class_expression: ClassExpression) -> None:
        """Initialize the model with a property expression and class expression."""
        super().__init__(
            property_expression, class_expression, object_expression_predicate=OWL.someValuesFrom
        )


class ObjectAllValuesFrom(_Restriction):
    """A class expression defined in `8.2.2  Universal Quantification <https://www.w3.org/TR/owl2-syntax/# Universal_Quantification>`_."""

    def __init__(self, property_expression: Nodeable, class_expression: ClassExpression) -> None:
        """Initialize the model with a property expression and class expression."""
        super().__init__(
            property_expression, class_expression, object_expression_predicate=OWL.allValuesFrom
        )


class ObjectHasValue(_Restriction):
    """A class expression defined in `8.2.3 Individual Value Restriction <https://www.w3.org/TR/owl2-syntax/#Individual_Value_Restriction>`_."""

    def __init__(self, property_expression: Nodeable, individual: Individual) -> None:
        """Initialize the model with a property expression and an individual."""
        super().__init__(property_expression, individual, object_expression_predicate=OWL.hasValue)


class ObjectHasSelf(_Restriction):
    """A class expression defined in `8.2.4 Self-Restriction <https://www.w3.org/TR/owl2-syntax/#Self-Restriction>`_."""

    def __init__(self, property_expression: Nodeable) -> None:
        """Initialize the model with a property expression."""
        super().__init__(
            property_expression, term.Literal(True), object_expression_predicate=OWL.hasSelf
        )

    def _funowl_inside(self) -> str:
        return self.property_expression.to_funowl()


class _Cardinality(ClassExpression):
    def __init__(
        self,
        n: int,
        property_expression: Nodeable,
        object_expression: Nodeable | None = None,
        *,
        property_qualified: term.Node,
        property_unqualified: term.Node,
        ppp: term.Node,
    ) -> None:
        self.n = n
        self.property_expression = property_expression
        self.object_expression = object_expression
        self.property_qualified = property_qualified
        self.property_unqualified = property_unqualified
        self.ppp = ppp

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


class _ObjCardinality(_Cardinality):
    """A grouping class for object cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    def __init__(
        self,
        n: int,
        property_expression: Nodeable,
        class_expression: ClassExpression | None = None,
        *,
        property_qualified: term.Node,
        property_unqualified: term.Node,
    ) -> None:
        super().__init__(
            n=n,
            property_expression=property_expression,
            object_expression=class_expression,
            property_qualified=property_qualified,
            property_unqualified=property_unqualified,
            ppp=OWL.onClass,
        )


class _DataCardinality(_Cardinality):
    """A grouping class for data cardinality models.

    The three subclasses only differ by the qualified and unqualified
    ranges used.
    """

    def __init__(
        self,
        n: int,
        data_property_expression: Nodeable,
        data_range: Nodeable | None = None,
        *,
        property_qualified: term.Node,
        property_unqualified: term.Node,
    ) -> None:
        super().__init__(
            n=n,
            property_expression=data_property_expression,
            object_expression=data_range,
            property_qualified=property_qualified,
            property_unqualified=property_unqualified,
            ppp=OWL.onDataRange,
        )


class ObjectMinCardinality(_ObjCardinality):
    """A class expression defined in `8.3.1 Minimum Cardinality <https://www.w3.org/TR/owl2-syntax/#Minimum_Cardinality>`_."""

    def __init__(
        self, n: int, property_expression: Nodeable, class_expression: ClassExpression | None = None
    ) -> None:
        """Initialize the model with a property expression, class expression, and cardinality."""
        super().__init__(
            n,
            property_expression,
            class_expression=class_expression,
            property_qualified=OWL.maxQualifiedCardinality,
            property_unqualified=OWL.maxCardinality,
        )


class ObjectMaxCardinality(_ObjCardinality):
    """A class expression defined in `8.3.2 Maximum Cardinality <https://www.w3.org/TR/owl2-syntax/#Maximum_Cardinality>`_."""

    def __init__(
        self, n: int, property_expression: Nodeable, class_expression: ClassExpression | None = None
    ) -> None:
        """Initialize the model with a property expression, class expression, and cardinality."""
        super().__init__(
            n,
            property_expression,
            class_expression=class_expression,
            property_qualified=OWL.minQualifiedCardinality,
            property_unqualified=OWL.minCardinality,
        )


class ObjectExactCardinality(_ObjCardinality):
    """A class expression defined in `8.3.2 Exact Cardinality <https://www.w3.org/TR/owl2-syntax/#Exact_Cardinality>`_."""

    def __init__(
        self, n: int, property_expression: Nodeable, class_expression: ClassExpression | None = None
    ) -> None:
        """Initialize the model with a property expression, class expression, and cardinality."""
        super().__init__(
            n,
            property_expression,
            class_expression=class_expression,
            property_qualified=OWL.qualifiedCardinality,
            property_unqualified=OWL.cardinality,
        )


class _DataValuesFrom(ClassExpression):
    """A class expression defined in https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2."""

    def __init__(
        self,
        data_property_expressions: list[Nodeable],
        data_range_expression: Nodeable,
        property: term.Node,
    ) -> None:
        self.data_property_expressions = data_property_expressions
        self.data_range_expression = data_range_expression
        self.property = property

    def to_rdflib_node(self, graph: Graph) -> term.BNode:
        node = term.BNode()
        graph.add((node, RDF.type, OWL.Restriction))
        if len(self.data_property_expressions) >= 2:
            p_o = OWL.onProperties, make_sequence(graph, self.data_property_expressions)
        else:
            p_o = OWL.onProperty, self.data_property_expressions[0].to_rdflib_node(graph)
        graph.add((node, self.property, self.data_range_expression.to_rdflib_node(graph)))
        graph.add((node, *p_o))
        return node

    def _funowl_inside(self) -> str:
        first = " ".join(dpe.to_funowl() for dpe in self.data_property_expressions)
        return f"{first} {self.data_range_expression.to_funowl()}"


class DataSomeValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.1 Existential Qualifications <https://www.w3.org/TR/owl2-syntax/#Existential_Quantification_2>`_."""

    def __init__(
        self, data_property_expressions: list[Nodeable], data_range_expression: Nodeable
    ) -> None:
        super().__init__(
            data_property_expressions=data_property_expressions,
            data_range_expression=data_range_expression,
            property=OWL.someValuesFrom,
        )


class DataAllValuesFrom(_DataValuesFrom):
    """A class expression defined in `8.4.2 Universal Qualifications <https://www.w3.org/TR/owl2-syntax/#Universal_Quantification_2>`_."""

    def __init__(
        self, data_property_expressions: list[Nodeable], data_range_expression: Nodeable
    ) -> None:
        super().__init__(
            data_property_expressions=data_property_expressions,
            data_range_expression=data_range_expression,
            property=OWL.allValuesFrom,
        )


class DataHasValue(_DataValuesFrom):
    """A class expression defined in `8.4.3 Literal Value Restriction <https://www.w3.org/TR/owl2-syntax/#Literal_Value_Restriction>`_."""

    def __init__(self, data_property_expression: Nodeable, literal: term.Literal) -> None:
        super().__init__(
            data_property_expressions=[data_property_expression],
            data_range_expression=literal,
            property=OWL.hasValue,
        )

    def _funowl_inside(self) -> str:
        first = " ".join(dpe.to_funowl() for dpe in self.data_property_expressions)
        return f"{first} {_literal_to_funowl(self.data_range_expression)}"


class DataMinCardinality(_DataCardinality):
    """A class expression defined in `8.5.1 Minimum Cardinality <https://www.w3.org/TR/owl2-syntax/#Minimum_Cardinality_2>`_."""

    def __init__(
        self,
        n: int,
        data_property_expression: Nodeable,
        data_range: Nodeable | None = None,
    ) -> None:
        """Initialize the model with a data property expression, data range expression, and cardinality."""
        super().__init__(
            n,
            data_property_expression,
            data_range,
            property_qualified=OWL.minQualifiedCardinality,
            property_unqualified=OWL.minCardinality,
        )


class DataMaxCardinality(_DataCardinality):
    """A class expression defined in `8.5.2 Maximum Cardinality <https://www.w3.org/TR/owl2-syntax/#Maximum_Cardinality_2>`_."""

    def __init__(
        self,
        n: int,
        data_property_expression: Nodeable,
        data_range: Nodeable | None = None,
    ) -> None:
        """Initialize the model with a data property expression, data range expression, and cardinality."""
        super().__init__(
            n,
            data_property_expression,
            data_range,
            property_qualified=OWL.maxQualifiedCardinality,
            property_unqualified=OWL.maxCardinality,
        )


class DataExactCardinality(_DataCardinality):
    """A class expression defined in `8.5.3 Exact Cardinality <https://www.w3.org/TR/owl2-syntax/#Exact_Cardinality_2>`_."""

    def __init__(
        self, n: int, data_property_expression: Nodeable, data_range: Nodeable | None = None
    ) -> None:
        """Initialize the model with a data property expression, data range expression, and cardinality."""
        super().__init__(
            n,
            data_property_expression,
            data_range,
            property_qualified=OWL.qualifiedCardinality,
            property_unqualified=OWL.cardinality,
        )


"""
`Section 9: Axioms <https://www.w3.org/TR/owl2-syntax/#Axioms>`_
"""
