"""Tests for functional OWL."""

import unittest

from curies import Reference
from rdflib import Graph, term

from pyobo.struct.func import (
    DataAllValuesFrom,
    DataComplementOf,
    DataExactCardinality,
    DataHasValue,
    DataIntersectionOf,
    DataMaxCardinality,
    DataMinCardinality,
    DataOneOf,
    DataSomeValuesFrom,
    DatatypeRestriction,
    DataUnionOf,
    Declaration,
    Nodeable,
    ObjectAllValuesFrom,
    ObjectComplementOf,
    ObjectExactCardinality,
    ObjectHasSelf,
    ObjectHasValue,
    ObjectIntersectionOf,
    ObjectMaxCardinality,
    ObjectMinCardinality,
    ObjectSomeValuesFrom,
    ObjectUnionOf,
    SimpleDateRange,
)


class FunctionalReference(Nodeable, Reference):
    def to_rdflib_node(self, graph: Graph) -> term.Node:
        return term.URIRef(self.bioregistry_link)

    def to_funowl(self) -> str:
        return self.curie

    def _funowl_inside(self) -> str:
        raise NotImplementedError


def _c(c) -> FunctionalReference:
    return FunctionalReference.from_curie(c)


class TestSection5(unittest.TestCase):
    """Test Section 5."""

    def test_declarations(self):
        """Test declarations."""
        decl = Declaration(_c("owl:Thing"), "Class")
        self.assertEqual("Declaration( Class( owl:Thing ) )", decl.to_funowl())

        decl = Declaration(_c("owl:topObjectProperty"), "ObjectProperty")
        self.assertEqual("Declaration( ObjectProperty( owl:topObjectProperty ) )", decl.to_funowl())

        decl = Declaration(_c("owl:topDataProperty"), "DataProperty")
        self.assertEqual("Declaration( DataProperty( owl:topDataProperty ) )", decl.to_funowl())

        decl = Declaration(_c("rdfs:Literal"), "Datatype")
        self.assertEqual("Declaration( Datatype( rdfs:Literal ) )", decl.to_funowl())

        decl = Declaration(_c("rdfs:label"), "AnnotationProperty")
        self.assertEqual("Declaration( AnnotationProperty( rdfs:label ) )", decl.to_funowl())

        decl = Declaration(_c("a:Peter"), "NamedIndividual")
        self.assertEqual("Declaration( NamedIndividual( a:Peter ) )", decl.to_funowl())


class TestSection7(unittest.TestCase):
    """Test Section 7: Data Ranges."""

    def test_it(self):
        expr = DataIntersectionOf(
            [
                SimpleDateRange(_c("xsd:nonNegativeInteger")),
                SimpleDateRange(_c("xsd:nonPositiveInteger")),
            ]
        )
        self.assertEqual(
            "DataIntersectionOf( xsd:nonNegativeInteger xsd:nonPositiveInteger )", expr.to_funowl()
        )

        expr = DataUnionOf(
            [
                SimpleDateRange(_c("xsd:string")),
                SimpleDateRange(_c("xsd:integer")),
            ]
        )
        self.assertEqual("DataUnionOf( xsd:string xsd:integer )", expr.to_funowl())

        expr = DataComplementOf(SimpleDateRange(_c("xsd:integer")))
        self.assertEqual("DataComplementOf( xsd:integer )", expr.to_funowl())

        expr = DataOneOf(
            [
                term.Literal("Peter"),
                term.Literal(1),
            ]
        )
        self.assertEqual('DataOneOf( "Peter" "1"^^xsd:integer )', expr.to_funowl())

        expr = DatatypeRestriction(
            _c("xsd:integer"),
            [
                (_c("xsd:minInclusive"), term.Literal(5)),
                (_c("xsd:maxExclusive"), term.Literal(10)),
            ],
        )
        self.assertEqual(
            'DatatypeRestriction( xsd:integer xsd:minInclusive "5"^^xsd:integer xsd:maxExclusive "10"^^xsd:integer )',
            expr.to_funowl(),
        )


class TestSection8ClassExpressions(unittest.TestCase):
    """Test Section 8: Class Expressions."""

    def test_object_propositional(self):
        """Test propositional lists."""
        expr = ObjectIntersectionOf([_c("a:Dog"), _c("a:CanTalk")])
        self.assertEqual("ObjectIntersectionOf( a:Dog a:CanTalk )", expr.to_funowl())
        expr = ObjectUnionOf([_c("a:Man"), _c("a:Woman")])
        self.assertEqual("ObjectUnionOf( a:Man a:Woman )", expr.to_funowl())
        expr = ObjectComplementOf(_c("a:Bird"))
        self.assertEqual("ObjectComplementOf( a:Bird )", expr.to_funowl())

    def test_object_restrictions(self):
        """Test object restrictions."""
        expr = ObjectSomeValuesFrom(_c("a:hasPet"), _c("a:Mongrel"))
        self.assertEqual("ObjectSomeValuesFrom( a:hasPet a:Mongrel )", expr.to_funowl())

        expr = ObjectAllValuesFrom(_c("a:hasPet"), _c("a:Dog"))
        self.assertEqual("ObjectAllValuesFrom( a:hasPet a:Dog )", expr.to_funowl())

        expr = ObjectHasValue(_c("a:fatherOf"), _c("a:Stewie"))
        self.assertEqual("ObjectHasValue( a:fatherOf a:Stewie )", expr.to_funowl())

        expr = ObjectHasSelf(_c("a:likes"))
        self.assertEqual("ObjectHasSelf( a:likes )", expr.to_funowl())

    def test_object_cardinality(self):
        """Test object restrictions."""
        expr = ObjectMinCardinality(2, _c("a:fatherOf"), _c("a:Man"))
        self.assertEqual("ObjectMinCardinality( 2 a:fatherOf a:Man )", expr.to_funowl())

        expr = ObjectMaxCardinality(2, _c("a:hasPet"))
        self.assertEqual("ObjectMaxCardinality( 2 a:hasPet )", expr.to_funowl())

        expr = ObjectExactCardinality(1, _c("a:hasPet"), _c("a:Dog"))
        self.assertEqual("ObjectExactCardinality( 1 a:hasPet a:Dog )", expr.to_funowl())

    def test_data_restrictions(self):
        """Test object restrictions."""
        expr = DataSomeValuesFrom(
            [_c("a:hasAge")],
            DatatypeRestriction(_c("xsd:integer"), [(_c("xsd:maxExclusive"), term.Literal(20))]),
        )
        self.assertEqual(
            'DataSomeValuesFrom( a:hasAge DatatypeRestriction( xsd:integer xsd:maxExclusive "20"^^xsd:integer ) )',
            expr.to_funowl(),
        )

        expr = DataAllValuesFrom([_c("a:hasZIP")], _c("xsd:integer"))
        self.assertEqual("DataAllValuesFrom( a:hasZIP xsd:integer )", expr.to_funowl())

        expr = DataHasValue(_c("a:hasAge"), term.Literal(17))
        self.assertEqual('DataHasValue( a:hasAge "17"^^xsd:integer )', expr.to_funowl())

    def test_data_cardinality(self):
        """Test outputting data cardinality constraints."""
        r = _c("rdfs:label")

        expr = DataExactCardinality(1, r)
        self.assertEqual("DataExactCardinality( 1 rdfs:label )", expr.to_funowl())

        expr = DataMinCardinality(1, r)
        self.assertEqual("DataMinCardinality( 1 rdfs:label )", expr.to_funowl())

        expr = DataMaxCardinality(5, r)
        self.assertEqual("DataMaxCardinality( 5 rdfs:label )", expr.to_funowl())


class TestSection9Axioms(unittest.TestCase):
    """Test Section 9: Axioms."""
