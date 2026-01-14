"""Tests for functional OWL."""

import unittest

import rdflib
from curies import Converter, Reference
from rdflib import OWL, RDF, RDFS, XSD, Graph, Namespace, compare, term

from pyobo.struct.functional import dsl as f
from pyobo.struct.functional import macros as m
from pyobo.struct.functional.dsl import (
    IdentifierBox,
    SimpleDataPropertyExpression,
    _get_data_value_po,
    _make_sequence_nodes,
    _safe_primitive_box,
    _yield_connector_nodes,
)
from pyobo.struct.functional.ontology import get_rdf_graph_oracle
from pyobo.struct.functional.utils import EXAMPLE_PREFIX_MAP, get_rdf_graph


class TestBox(unittest.TestCase):
    """Test boxes."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class."""
        cls.converter = Converter.from_prefix_map({"a": "https://example.org/a:"})

    def test_identifier_box(self) -> None:
        """Test the identifier box."""
        uri = term.URIRef("https://example.org/a:b")

        b1 = f.IdentifierBox("a:b")
        self.assertIsInstance(b1.identifier, Reference)
        self.assertEqual("a:b", b1.identifier.curie)
        self.assertEqual("a:b", b1.to_funowl())
        self.assertEqual(uri, b1.to_rdflib_node(Graph(), self.converter))

        b2 = f.IdentifierBox(Reference.from_curie("a:b"))
        self.assertIsInstance(b2.identifier, Reference)
        self.assertEqual("a:b", b2.identifier.curie)
        self.assertEqual("a:b", b2.to_funowl())
        self.assertEqual(uri, b2.to_rdflib_node(Graph(), self.converter))

        b4 = f.IdentifierBox(b1)
        self.assertIsInstance(b4.identifier, Reference)
        self.assertEqual("a:b", b4.identifier.curie)
        self.assertEqual("a:b", b4.to_funowl())
        self.assertEqual(uri, b4.to_rdflib_node(Graph(), self.converter))

        b3 = f.IdentifierBox(RDF.type)
        self.assertIsInstance(b3.identifier, term.URIRef)
        self.assertEqual("<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>", b3.to_funowl())
        self.assertEqual(RDF.type, b3.to_rdflib_node(Graph(), self.converter))

        b5 = f.IdentifierBox(b3)
        self.assertIsInstance(b5.identifier, term.URIRef)
        self.assertEqual("<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>", b5.to_funowl())
        self.assertEqual(RDF.type, b5.to_rdflib_node(Graph(), self.converter))

        b6 = _safe_primitive_box(Reference.from_curie("a:b"))
        self.assertIsInstance(b6, IdentifierBox)
        self.assertIsInstance(b6.identifier, Reference)

        b7 = _safe_primitive_box(RDF.type)
        self.assertIsInstance(b7, IdentifierBox)
        self.assertIsInstance(b7.identifier, term.URIRef)

        with self.assertRaises(TypeError):
            f.IdentifierBox(5)

        with self.assertRaises(RuntimeError):
            b1.to_funowl_args()

    def test_literal_box(self) -> None:
        """Test the literal box."""
        with self.assertRaises(TypeError):
            f.LiteralBox(object())

        b1 = f.LiteralBox(1)
        self.assertEqual('"1"^^xsd:integer', b1.to_funowl())
        self.assertEqual(term.Literal(1), b1.to_rdflib_node(Graph(), self.converter))

        b2 = f.LiteralBox(term.Literal(1))
        self.assertEqual('"1"^^xsd:integer', b2.to_funowl())
        self.assertEqual(term.Literal(1), b2.to_rdflib_node(Graph(), self.converter))

        b3 = f.LiteralBox(b1)
        self.assertEqual('"1"^^xsd:integer', b3.to_funowl())
        self.assertEqual(term.Literal(1), b3.to_rdflib_node(Graph(), self.converter))

    def test_literal_box_boolean(self) -> None:
        """Test the literal box with booleans."""
        b4 = f.LiteralBox(True)
        self.assertEqual('"true"^^xsd:boolean', b4.to_funowl())
        literal = b4.to_rdflib_node(Graph(), self.converter)
        self.assertIsInstance(literal, term.Literal)
        self.assertEqual(XSD.boolean, literal.datatype)
        self.assertEqual(term.Literal(True), literal)

        b42 = f.LiteralBox(False)
        self.assertEqual('"false"^^xsd:boolean', b42.to_funowl())
        self.assertEqual(term.Literal(False), b42.to_rdflib_node(Graph(), self.converter))

    def test_literal_box_with_language(self) -> None:
        """Test the litereal box with language."""
        b5 = f.LiteralBox(term.Literal("hallo", lang="de"))
        self.assertEqual('"hallo"@de', b5.to_funowl())
        self.assertEqual(
            term.Literal("hallo", lang="de"), b5.to_rdflib_node(Graph(), self.converter)
        )

        b6 = f.LiteralBox("hallo", language="de")
        self.assertEqual('"hallo"@de', b6.to_funowl())
        self.assertEqual(
            term.Literal("hallo", lang="de"), b6.to_rdflib_node(Graph(), self.converter)
        )


class TestSection5(unittest.TestCase):
    """Test Section 5."""

    def test_declarations(self):
        """Test declarations."""
        decl = f.Declaration("owl:Thing", "Class")
        self.assertEqual("Declaration(Class(owl:Thing))", decl.to_funowl())

        decl = f.Declaration("owl:topObjectProperty", "ObjectProperty")
        self.assertEqual("Declaration(ObjectProperty(owl:topObjectProperty))", decl.to_funowl())

        decl = f.Declaration("owl:topDataProperty", "DataProperty")
        self.assertEqual("Declaration(DataProperty(owl:topDataProperty))", decl.to_funowl())

        decl = f.Declaration("rdfs:Literal", "Datatype")
        self.assertEqual("Declaration(Datatype(rdfs:Literal))", decl.to_funowl())

        decl = f.Declaration("rdfs:label", "AnnotationProperty")
        self.assertEqual("Declaration(AnnotationProperty(rdfs:label))", decl.to_funowl())

        decl = f.Declaration("a:Peter", "NamedIndividual")
        self.assertEqual("Declaration(NamedIndividual(a:Peter))", decl.to_funowl())


class TestSection7(unittest.TestCase):
    """Test Section 7: Data Ranges."""

    def test_data_ranges(self):
        """Test data ranges."""
        expr = f.DataIntersectionOf(
            [
                "xsd:nonNegativeInteger",
                "xsd:nonPositiveInteger",
            ]
        )
        self.assertEqual(
            "DataIntersectionOf(xsd:nonNegativeInteger xsd:nonPositiveInteger)", expr.to_funowl()
        )

        expr = f.DataUnionOf(["xsd:string", "xsd:integer"])
        self.assertEqual("DataUnionOf(xsd:string xsd:integer)", expr.to_funowl())

        expr = f.DataComplementOf("xsd:integer")
        self.assertEqual("DataComplementOf(xsd:integer)", expr.to_funowl())

        expr = f.DataOneOf(
            [
                f.LiteralBox("Peter"),
                f.LiteralBox(1),
            ]
        )
        self.assertEqual('DataOneOf("Peter" "1"^^xsd:integer)', expr.to_funowl())

        expr = f.DatatypeRestriction(
            "xsd:integer",
            [
                ("xsd:minInclusive", f.LiteralBox(5)),
                ("xsd:maxExclusive", f.LiteralBox(10)),
            ],
        )
        self.assertEqual(
            'DatatypeRestriction(xsd:integer xsd:minInclusive "5"^^xsd:integer xsd:maxExclusive "10"^^xsd:integer)',
            expr.to_funowl(),
        )


class TestSection8ClassExpressions(unittest.TestCase):
    """Test Section 8: Class Expressions."""

    def test_object_propositional(self):
        """Test propositional lists."""
        expr = f.ObjectIntersectionOf(["a:Dog", "a:CanTalk"])
        self.assertEqual("ObjectIntersectionOf(a:Dog a:CanTalk)", expr.to_funowl())
        with self.assertRaises(ValueError):
            f.ObjectIntersectionOf(["a:Dog"])

        expr = f.ObjectUnionOf(["a:Man", "a:Woman"])
        self.assertEqual("ObjectUnionOf(a:Man a:Woman)", expr.to_funowl())
        with self.assertRaises(ValueError):
            f.ObjectUnionOf(["a:Dog"])

        expr = f.ObjectComplementOf("a:Bird")
        self.assertEqual("ObjectComplementOf(a:Bird)", expr.to_funowl())

    def test_object_restrictions(self):
        """Test object restrictions."""
        expr = f.ObjectSomeValuesFrom("a:hasPet", "a:Mongrel")
        self.assertEqual("ObjectSomeValuesFrom(a:hasPet a:Mongrel)", expr.to_funowl())

        expr = f.ObjectAllValuesFrom("a:hasPet", "a:Dog")
        self.assertEqual("ObjectAllValuesFrom(a:hasPet a:Dog)", expr.to_funowl())

        expr = f.ObjectHasValue("a:fatherOf", "a:Stewie")
        self.assertEqual("ObjectHasValue(a:fatherOf a:Stewie)", expr.to_funowl())

        expr = f.ObjectHasSelf("a:likes")
        self.assertEqual("ObjectHasSelf(a:likes)", expr.to_funowl())

    def test_object_cardinality(self):
        """Test object restrictions."""
        expr = f.ObjectMinCardinality(2, "a:fatherOf", "a:Man")
        self.assertEqual("ObjectMinCardinality(2 a:fatherOf a:Man)", expr.to_funowl())

        expr = f.ObjectMaxCardinality(2, "a:hasPet")
        self.assertEqual("ObjectMaxCardinality(2 a:hasPet)", expr.to_funowl())

        expr = f.ObjectExactCardinality(1, "a:hasPet", "a:Dog")
        self.assertEqual("ObjectExactCardinality(1 a:hasPet a:Dog)", expr.to_funowl())

    def test_data_restrictions(self):
        """Test object restrictions."""
        expr = f.DataSomeValuesFrom(
            ["a:hasAge"],
            f.DatatypeRestriction("xsd:integer", [("xsd:maxExclusive", term.Literal(20))]),
        )
        self.assertEqual(
            'DataSomeValuesFrom(a:hasAge DatatypeRestriction(xsd:integer xsd:maxExclusive "20"^^xsd:integer))',
            expr.to_funowl(),
        )

        expr = f.DataAllValuesFrom(["a:hasZIP"], "xsd:integer")
        self.assertEqual("DataAllValuesFrom(a:hasZIP xsd:integer)", expr.to_funowl())

        expr = f.DataHasValue("a:hasAge", term.Literal(17))
        self.assertEqual('DataHasValue(a:hasAge "17"^^xsd:integer)', expr.to_funowl())

    def test_data_cardinality(self):
        """Test outputting data cardinality constraints."""
        r = "rdfs:label"

        expr = f.DataExactCardinality(1, r)
        self.assertEqual("DataExactCardinality(1 rdfs:label)", expr.to_funowl())

        expr = f.DataMinCardinality(1, r)
        self.assertEqual("DataMinCardinality(1 rdfs:label)", expr.to_funowl())

        expr = f.DataMaxCardinality(5, r)
        self.assertEqual("DataMaxCardinality(5 rdfs:label)", expr.to_funowl())


class TestSection9Axioms(unittest.TestCase):
    """Test Section 9: Axioms."""

    def test_subclass_of(self):
        """Test subclass axioms."""
        expr = f.SubClassOf("a:Baby", "a:Child")
        self.assertEqual("SubClassOf(a:Baby a:Child)", expr.to_funowl())

        expr = f.SubClassOf(f.ObjectSomeValuesFrom("a:hasChild", "a:Child"), "a:Parent")
        self.assertEqual(
            "SubClassOf(ObjectSomeValuesFrom(a:hasChild a:Child) a:Parent)", expr.to_funowl()
        )

    def test_equivalent_classes(self):
        """Test equivalent class axioms."""
        expr = f.EquivalentClasses(["a:Boy", f.ObjectIntersectionOf(["a:Child", "a:Man"])])
        self.assertEqual(
            "EquivalentClasses(a:Boy ObjectIntersectionOf(a:Child a:Man))", expr.to_funowl()
        )

        expr = f.EquivalentClasses(["a:Boy", "a:Girl"])
        self.assertEqual("EquivalentClasses(a:Boy a:Girl)", expr.to_funowl())

        with self.assertRaises(ValueError):
            f.EquivalentClasses(["a:Boy"])

    def test_disjoint_union(self):
        """Test disjoint union axioms."""
        expr = f.DisjointUnion("a:Child", ["a:Boy", "a:Girl"])
        self.assertEqual("DisjointUnion(a:Child a:Boy a:Girl)", expr.to_funowl())

        with self.assertRaises(ValueError):
            f.DisjointUnion("a:Child", ["a:Boy"])

    def test_subproperties(self) -> None:
        """Test object sub-property."""
        expr = f.SubObjectPropertyOf("a:hasDog", "a:hasPet")
        self.assertEqual("SubObjectPropertyOf(a:hasDog a:hasPet)", expr.to_funowl())


class TestSection10(unittest.TestCase):
    """Test Section 9: Annotations."""

    def test_annotation_assertion(self):
        """Test AnnotationAssertion."""
        expected = 'AnnotationAssertion(rdfs:label a:Person "Represents the set of all people.")'
        expr = f.AnnotationAssertion(
            "rdfs:label", "a:Person", f.LiteralBox("Represents the set of all people.")
        )
        self.assertEqual(expected, expr.to_funowl())

        expected = 'AnnotationAssertion(Annotation(dc:terms orcid:0000-0003-4423-4370) rdfs:label a:Person "Represents the set of all people.")'
        expr = f.AnnotationAssertion(
            "rdfs:label",
            "a:Person",
            f.LiteralBox("Represents the set of all people."),
            annotations=[f.Annotation("dc:terms", "orcid:0000-0003-4423-4370")],
        )
        self.assertEqual(expected, expr.to_funowl())


class TestMiscellaneous(unittest.TestCase):
    """Test miscellaneous."""

    def test_value_errors(self) -> None:
        """Test misc. value errors for lists not long enough."""
        with self.assertRaises(ValueError):
            f.EquivalentDataProperties(["a:hasName"])
        with self.assertRaises(ValueError):
            f.EquivalentDataProperties([])
        with self.assertRaises(ValueError):
            f.EquivalentObjectProperties(["a:ope1"])
        with self.assertRaises(ValueError):
            f.EquivalentObjectProperties([])
        with self.assertRaises(ValueError):
            f.DisjointClasses(["a:Man"])
        with self.assertRaises(ValueError):
            f.DisjointClasses([])
        with self.assertRaises(ValueError):
            f.ObjectOneOf(["a:Peter"])
        with self.assertRaises(ValueError):
            f.ObjectOneOf([])
        with self.assertRaises(NotImplementedError):
            f.DataSomeValuesFrom(["a:hasAge", "a:dpe2"], "a:dr")
        with self.assertRaises(ValueError):
            f.DataSomeValuesFrom([], "a:dr")

    def test_data_value_rdf(self) -> None:
        """Test the data value RDF generation."""
        graph = Graph()
        converter = Converter.from_prefix_map(EXAMPLE_PREFIX_MAP)
        dpes = [SimpleDataPropertyExpression("a:dpe1"), SimpleDataPropertyExpression("a:dpe2")]
        rv = _get_data_value_po(graph=graph, converter=converter, dpes=dpes)
        self.assertEqual(OWL.onProperties, rv[0])

    def test_make_sequence_nodes(self) -> None:
        """Test making a sequence."""
        ex = Namespace("https://example.org/")

        g1 = Graph()
        rv1 = _make_sequence_nodes(g1, [])
        self.assertEqual(RDF.nil, rv1)

        g2 = Graph()
        rv2 = _make_sequence_nodes(g2, [ex["1"]])
        self.assertNotEqual(RDF.nil, rv2)

        g3 = Graph()
        input_list = [ex["1"], ex["2"], ex["3"]]
        rv3 = _make_sequence_nodes(g3, input_list, type_connector_nodes=True)
        self.assertNotEqual(RDF.nil, rv3)
        self.assertEqual(len(input_list), len(list(_yield_connector_nodes(g3, rv3))))

    def test_passthrough(self) -> None:
        """Test passthrough."""

        class CompoundDPE(f.DataPropertyExpression):
            """A dummpy data property expression."""

            def to_funowl_args(self) -> str:
                """Return an empty string."""
                return ""

            def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
                """Return a blank node."""
                return term.BNode()

        dpe2 = CompoundDPE()
        passthrough = f.DataPropertyExpression.safe(dpe2)
        self.assertIsInstance(passthrough, CompoundDPE)

    def test_creation_skip(self) -> None:
        """Test skipping of declaration on builtins."""
        converter = Converter([])

        graph = Graph()
        spe = SimpleDataPropertyExpression(OWL.topDataProperty)
        spe.to_rdflib_node(graph, converter)
        self.assertNotIn((OWL.topDataProperty, RDF.type, OWL.DataRange), graph)

        graph2 = Graph()
        ope = f.SimpleObjectPropertyExpression(OWL.topObjectProperty)
        ope.to_rdflib_node(graph2, converter)
        self.assertNotIn((OWL.topObjectProperty, RDF.type, OWL.ObjectProperty), graph2)

        graph3 = Graph()
        ap = f.AnnotationProperty(RDFS.label)
        ap.to_rdflib_node(graph3, converter)
        self.assertNotIn((RDFS.label, RDF.type, OWL.AnnotationProperty), graph3)

        graph4 = Graph()
        ce = f.SimpleClassExpression(OWL.Thing)
        ce.to_rdflib_node(graph4, converter)
        self.assertNotIn((OWL.Thing, RDF.type, OWL.Class), graph4)


class TestRDF(unittest.TestCase):
    """Test serialization to RDF."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the serialization test case."""
        cls.axiom_examples: list[f.Axiom] = [
            f.ClassAssertion(
                f.DataSomeValuesFrom(
                    ["a:hasAge"], f.DatatypeRestriction("xsd:integer", [("xsd:maxExclusive", 20)])
                ),
                "a:Meg",
            ),
            f.Declaration("a:test", "Class"),
            f.Declaration("a:test", "ObjectProperty"),
            f.Declaration("a:test", "DataProperty"),
            f.Declaration("a:test", "AnnotationProperty"),
            f.Declaration("a:test", "Datatype"),
            f.Declaration("a:test", "NamedIndividual"),
            f.DatatypeDefinition("a:Test", f.DataOneOf(["Peter", 1])),
            f.DatatypeDefinition(
                "a:Test", f.DataIntersectionOf(["xsd:integer", "xsd:nonNegativeInteger"])
            ),
            f.DatatypeDefinition(
                "a:Test", f.DataIntersectionOf(["xsd:integer", f.DataOneOf([1, 2, 3])])
            ),
            f.DatatypeDefinition(
                "a:Test", f.DataUnionOf(["xsd:integer", f.DataOneOf([f.l("a"), f.l("b")])])
            ),
            f.DatatypeDefinition("a:Test", f.DataUnionOf(["xsd:integer", "xsd:string"])),
            f.DatatypeDefinition("a:Test", f.DataComplementOf("xsd:nonNegativeInteger")),
            f.SubClassOf(
                f.ObjectSomeValuesFrom("a:ope1", "owl:Thing"), "a:ce1"
            ),  # 9.2.5 object property domain
            f.SubClassOf(
                "owl:Thing", f.ObjectAllValuesFrom("a:ope1", "a:ce1")
            ),  # 9.2.6 object property range
            f.SubClassOf("owl:Thing", f.ObjectHasSelf("a:ope1")),  # reflexive
            f.SubClassOf(f.ObjectHasSelf("a:ope1"), "owl:Nothing"),  # irreflexive
            f.SubObjectPropertyOf("a:ope1", f.ObjectInverseOf("a:ope1")),  # symmetric
            f.SubObjectPropertyOf(
                f.ObjectPropertyChain(["a:ope1", "a:ope1"]), "a:op1"
            ),  # transitive definition
            f.ClassAssertion(f.ObjectMaxCardinality(1, "a:hasPet"), "a:Peter"),
            f.ClassAssertion(f.ObjectIntersectionOf(["a:Dog", "a:canTalk"]), "a:Brian"),
            # FIXME this breaks if order is Dog, Cat
            f.ClassAssertion(f.ObjectUnionOf(["a:Cat", "a:Dog"]), "a:Brian"),
            f.ClassAssertion(
                f.ObjectSomeValuesFrom(
                    "a:hasChild",
                    f.ObjectIntersectionOf(
                        [
                            # FIXME this breaks if these are out of sort order
                            f.ObjectHasValue("a:hasChild", "a:Chris"),
                            f.ObjectHasValue("a:hasChild", "a:Meg"),
                            f.ObjectHasValue("a:hasChild", "a:Stewie"),
                        ]
                    ),
                ),
                "a:Francis",
            ),
            f.ClassAssertion(f.ObjectMaxCardinality(1, "a:hasPet"), "a:Peter"),
            f.ClassAssertion(f.ObjectMinCardinality(2, "a:fatherOf", "a:Man"), "a:Peter"),
            f.SubClassOf(
                "owl:Thing", f.ObjectMaxCardinality(1, f.ObjectInverseOf("a:ope1"))
            ),  # inverse functional
            f.SubClassOf("owl:Thing", f.ObjectMaxCardinality(1, "a:ope1")),  # functional
            f.SubClassOf("owl:Thing", f.ObjectExactCardinality(1, f.ObjectInverseOf("a:ope1"))),
            f.SubClassOf("owl:Thing", f.ObjectMinCardinality(1, f.ObjectInverseOf("a:ope1"))),
            f.SubObjectPropertyOf("a:ope1", f.ObjectInverseOf("a:ope2")),
            f.SubObjectPropertyOf(f.ObjectInverseOf("a:ope1"), "a:ope2"),
            f.EquivalentObjectProperties(["a:ope1", f.ObjectInverseOf("a:ope2")]),
            f.ClassAssertion(f.DataHasValue("a:hasAge", 17), "a:Meg"),
            f.ClassAssertion(f.DataHasValue("a:hasHairColor", f.l("brown")), "a:Meg"),
            f.EquivalentClasses(["a:Boy", "a:Girl"]),
            # do the griffin parent both ways to see if sorting is happening in ROBOT
            f.EquivalentClasses(["a:GriffinParent", f.ObjectOneOf(["a:Peter", "a:Lois"])]),
            f.EquivalentClasses(["a:GriffinParent", f.ObjectOneOf(["a:Lois", "a:Peter"])]),
            f.EquivalentClasses(
                [
                    "a:GriffinFamilyMember",
                    f.ObjectOneOf("a:Peter a:Lois a:Stewie a:Meg a:Chris a:Brian".split()),
                ]
            ),
            f.SubClassOf("owl:Thing", f.DataMaxCardinality(1, "a:hasAge")),
            f.SubClassOf("owl:Thing", f.DataExactCardinality(1, "a:hasAge")),
            f.SubClassOf("owl:Thing", f.DataMinCardinality(1, "a:hasAge")),
            f.SubClassOf("a:Dog", "a:Pet"),
            f.SubClassOf("a:Dog", "owl:Thing"),
            f.SubObjectPropertyOf("a:hasDog", "a:hasPet"),
            f.SubObjectPropertyOf(
                "a:hasDog",
                "a:hasPet",
                annotations=[f.Annotation("dcterms:contributor", "orcid:0000-0003-4423-4370")],
            ),
            f.AnnotationAssertion("rdfs:label", "a:Dog", f.l("dog")),
            f.AnnotationAssertion("a:ap1", "a:Dog", f.l("dog")),
            f.AnnotationPropertyRange("a:hasPet", "a:Pet"),
            f.AnnotationPropertyDomain("a:hasPet", "a:Person"),
            f.AsymmetricObjectProperty("a:hasParent"),
            f.FunctionalObjectProperty("a:hasFather"),
            f.InverseFunctionalObjectProperty("a:fatherOf"),
            f.ReflexiveObjectProperty("a:knows"),
            f.IrreflexiveObjectProperty("a:marriedTo"),
            f.SymmetricObjectProperty("a:friend"),
            f.TransitiveObjectProperty("a:ancestorOf"),
            f.DataPropertyDomain("a:hasName", "a:Person"),
            f.DataPropertyRange("a:hasName", "xsd:string"),
            f.ObjectPropertyDomain("a:hasDog", "a:Person"),
            f.ObjectPropertyRange("a:hasDog", "a:Dog"),
            f.SameIndividual(["a:Peter", "a:Peter_Griffin"]),
            f.DifferentIndividuals(
                [
                    "a:Meg",
                    "a:Peter",
                ]
            ),  # sort order matters to match ROBOT
            f.DifferentIndividuals(
                ["a:Lois", "a:Meg", "a:Peter"]
            ),  # sort order matters to match ROBOT
            f.EquivalentDataProperties(["a:hasName", "a:seLlama"]),
            f.EquivalentObjectProperties(["a:hasBrother", "a:hasMaleSibling"]),
            f.FunctionalDataProperty("a:hasAge"),
            f.InverseObjectProperties("a:hasFather", "a:fatherOf"),
            f.DisjointUnion("a:Child", ["a:Boy", "a:Girl"]),
            f.ClassAssertion("a:Child", "a:Stewie"),
            f.ClassAssertion(f.ObjectComplementOf("a:Girl"), "a:Stewie"),
            f.DataPropertyAssertion("a:hasLastName", "a:Peter", f.l("Griffin")),
            f.DatatypeDefinition(
                "a:SSN",
                f.DatatypeRestriction(
                    "xsd:string", [("xsd:pattern", "[0-9]{3}-[0-9]{2}-[0-9]{4}")]
                ),
            ),
            f.DisjointClasses(["a:Man", "a:Woman"]),
            f.DisjointClasses(
                ["a:Man", "a:Marsupial", "a:Woman"]
            ),  # sort order matters to match ROBOT
            f.SubDataPropertyOf("a:hasLastName", "a:hasName"),
            f.SubAnnotationPropertyOf("a:brandName", "a:synonymType"),
            f.ObjectPropertyAssertion("a:parentOf", "a:Peter", "a:Chris"),
            f.ObjectPropertyAssertion(f.ObjectInverseOf("a:hasParent"), "a:Peter", "a:Chris"),
            f.NegativeDataPropertyAssertion("a:hasAge", "a:Meg", 5),
            f.NegativeObjectPropertyAssertion("a:hasSon", "a:Peter", "a:Meg"),
            f.NegativeObjectPropertyAssertion(f.ObjectInverseOf("a:sonOf"), "a:Meg", "a:Peter"),
            f.DisjointDataProperties(["a:hasName", "a:hasAddress"]),
            f.DisjointDataProperties(["a:hasName", "a:hasAddress", "a:hasBankAccount"]),
            f.DisjointObjectProperties(["a:hasFather", "a:hasMother"]),
            f.HasKey("owl:Thing", [], ["a:hasSSN"]),
            f.HasKey("owl:Thing", ["a:ope1"], ["a:dpe1"]),
            f.HasKey("owl:Thing", ["a:ope1", "a:ope2"], ["a:dpe1"]),
            f.HasKey("owl:Thing", ["a:ope1", "a:ope2"], []),
            f.HasKey("owl:Thing", ["a:ope1", "a:ope2"], ["a:dpe1", "a:dpe2"]),
            f.SubObjectPropertyOf(
                f.ObjectPropertyChain(["a:hasMother", "a:hasSister"]), "a:hasAunt"
            ),
            m.RelationshipMacro("a:16793", "a:0002160", "a:9606"),
            m.LabelMacro("a:16793", "RAET1E"),
            m.LabelMacro("a:16793", "RAET1E", language="en"),
            m.DescriptionMacro("a:16793", "retinoic acid early transcript 1E"),
            m.OBOConsiderMacro("a:16793", "a:16794"),
            m.IsOBOBuiltinMacro("a:1234"),
            m.IsOBOBuiltinMacro("a:1234", False),
            m.SynonymMacro("a:16793", "ULBP4", scope="EXACT", synonym_type="OMO:0003008"),
            m.SynonymMacro(
                "a:16793", "ULBP4", scope="EXACT", synonym_type="OMO:0003008", language="en"
            ),
            m.MappingMacro(
                "a:0619dd9e",
                "EXACT",
                "a:00000137",
                mapping_justification="semapv:ManualMappingCuration",
            ),
            m.XrefMacro("a:0619dd9e", "a:00000137"),
            m.TransitiveOver("a:0000066", "a:0000050"),
            m.DataPropertyMaxCardinality(1, "a:hasAge"),
        ]

    def test_class_intersection(self) -> None:
        """Test class intersection macro."""
        self.assert_rdf_equal(
            m.ClassIntersectionMacro(
                "ZFA:0000134", ["CL:0000540", ("BFO:0000050", "NCBITaxon:7955")]
            )
        )

    def test_has_examples(self) -> None:
        """Test all axiom types have at least one example."""
        axioms_types_with_examples: set[type[f.Axiom]] = {
            axiom.__class__ for axiom in self.axiom_examples
        }
        # these are intermediate classes and don't need examples
        skips = {
            f.Axiom,
            f.ClassAxiom,
            f.ObjectPropertyAxiom,
            f.AnnotationAxiom,
            f.DataPropertyAxiom,
            f.AnnotationPropertyTypingAxiom,
            f.Assertion,
        }
        missing_names = sorted(
            cls.__name__ for cls in _get_all_axiom_types() - axioms_types_with_examples - skips
        )
        if missing_names:
            msg = f"Missing {len(missing_names)} examples for the following axiom types:"
            for missing_name in missing_names:
                msg += f"\n- {missing_name}"
            self.fail(msg)

    def test_nested(self) -> None:
        """Test nested annotations."""
        prefix_map = {
            "agrovoc": "http://aims.fao.org/aos/agrovoc/",
            "agro": "http://purl.obolibrary.org/obo/AGRO_",
            "wd": "http://www.wikidata.org/entity/",
            "orcid": "https://orcid.org/",
            "sssom": "https://w3id.org/sssom/",
            "semapv": "https://w3id.org/semapv/vocab/",
            "dcterms": "http://purl.org/dc/terms/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "a": "https://example.org/a:",
        }
        a = f.AnnotationAssertion(
            "skos:exactMatch",
            "agrovoc:0619dd9e",
            "agro:00000137",
            annotations=[
                f.Annotation(
                    "dcterms:contributor",
                    "orcid:0000-0003-4423-4370",
                    annotations=[
                        f.Annotation("wd:P1416", "wd:Q126066280"),
                    ],
                ),
            ],
        )
        self.assert_rdf_equal(a, prefix_map)

        # test nesting 3 deep
        b = f.AnnotationAssertion(
            "skos:exactMatch",
            "agrovoc:0619dd9e",
            "agro:00000137",
            annotations=[
                f.Annotation(
                    "dcterms:contributor",
                    "orcid:0000-0003-4423-4370",
                    annotations=[
                        f.Annotation(
                            "wd:P1416",
                            "wd:Q126066280",
                            annotations=[
                                f.Annotation("a:ap1", "a:v1"),
                            ],
                        ),
                    ],
                ),
            ],
        )
        self.assert_rdf_equal(b, prefix_map)

    def assert_rdf_equal(self, box: f.Box, prefix_map: dict[str, str] | None = None) -> None:
        """Assert the RDF generated is the same as the OFN converted via robot."""
        if prefix_map is None:
            prefix_map = EXAMPLE_PREFIX_MAP
        try:
            a = get_rdf_graph([box], prefix_map=prefix_map)
        except NotImplementedError:
            a = rdflib.Graph()
        b = get_rdf_graph_oracle([box], prefix_map=prefix_map)
        if not compare.isomorphic(a, b):
            both, first, second = compare.graph_diff(a, b)
            msg = "\nTriples in both:\n\n"
            msg += dump_nt_sorted(both)
            if first:
                msg += "\n\nTriples generated _only_ by PyOBO:\n\n"
                msg += dump_nt_sorted(first)
            if second:
                msg += "\n\nTriples generated _only_ by ROBOT:\n\n"
                msg += dump_nt_sorted(second)
            self.fail(msg)

    def test_rdf(self) -> None:
        """Test serialization to RDF."""
        for axiom in self.axiom_examples:
            with self.subTest(axiom=axiom.to_funowl()):
                self.assert_rdf_equal(axiom, EXAMPLE_PREFIX_MAP)


def dump_nt_sorted(g: Graph) -> str:
    """Write all triples in a canonical way."""
    return "\n".join(line for line in sorted(g.serialize(format="nt").splitlines()) if line)


def _get_all_axiom_types() -> set[type[f.Axiom]]:
    rv: set[type[f.Axiom]] = set()
    for x in dir(f):
        if x.startswith("_"):
            continue
        t = getattr(f, x)
        try:
            if isinstance(t, type) and issubclass(t, f.Axiom):
                rv.add(t)
        except TypeError:
            pass  # this happens on py310 where issubclass doesn't work properly
    return rv
