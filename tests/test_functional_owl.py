"""Tests for functional OWL."""

import unittest

import rdflib
from rdflib import Graph, compare, term

from pyobo.struct.functional import dsl as f


class TestSection5(unittest.TestCase):
    """Test Section 5."""

    def test_declarations(self):
        """Test declarations."""
        decl = f.Declaration("owl:Thing", "Class")
        self.assertEqual("Declaration( Class( owl:Thing ) )", decl.to_funowl())

        decl = f.Declaration("owl:topObjectProperty", "ObjectProperty")
        self.assertEqual("Declaration( ObjectProperty( owl:topObjectProperty ) )", decl.to_funowl())

        decl = f.Declaration("owl:topDataProperty", "DataProperty")
        self.assertEqual("Declaration( DataProperty( owl:topDataProperty ) )", decl.to_funowl())

        decl = f.Declaration("rdfs:Literal", "Datatype")
        self.assertEqual("Declaration( Datatype( rdfs:Literal ) )", decl.to_funowl())

        decl = f.Declaration("rdfs:label", "AnnotationProperty")
        self.assertEqual("Declaration( AnnotationProperty( rdfs:label ) )", decl.to_funowl())

        decl = f.Declaration("a:Peter", "NamedIndividual")
        self.assertEqual("Declaration( NamedIndividual( a:Peter ) )", decl.to_funowl())


class TestSection7(unittest.TestCase):
    """Test Section 7: Data Ranges."""

    def test_it(self):
        expr = f.DataIntersectionOf(
            [
                "xsd:nonNegativeInteger",
                "xsd:nonPositiveInteger",
            ]
        )
        self.assertEqual(
            "DataIntersectionOf( xsd:nonNegativeInteger xsd:nonPositiveInteger )", expr.to_funowl()
        )

        expr = f.DataUnionOf(["xsd:string", "xsd:integer"])
        self.assertEqual("DataUnionOf( xsd:string xsd:integer )", expr.to_funowl())

        expr = f.DataComplementOf("xsd:integer")
        self.assertEqual("DataComplementOf( xsd:integer )", expr.to_funowl())

        expr = f.DataOneOf(
            [
                f.LiteralBox("Peter"),
                f.LiteralBox(1),
            ]
        )
        self.assertEqual('DataOneOf( "Peter" "1"^^xsd:integer )', expr.to_funowl())

        expr = f.DatatypeRestriction(
            "xsd:integer",
            [
                ("xsd:minInclusive", f.LiteralBox(5)),
                ("xsd:maxExclusive", f.LiteralBox(10)),
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
        expr = f.ObjectIntersectionOf(["a:Dog", "a:CanTalk"])
        self.assertEqual("ObjectIntersectionOf( a:Dog a:CanTalk )", expr.to_funowl())
        expr = f.ObjectUnionOf(["a:Man", "a:Woman"])
        self.assertEqual("ObjectUnionOf( a:Man a:Woman )", expr.to_funowl())
        expr = f.ObjectComplementOf("a:Bird")
        self.assertEqual("ObjectComplementOf( a:Bird )", expr.to_funowl())

    def test_object_restrictions(self):
        """Test object restrictions."""
        expr = f.ObjectSomeValuesFrom("a:hasPet", "a:Mongrel")
        self.assertEqual("ObjectSomeValuesFrom( a:hasPet a:Mongrel )", expr.to_funowl())

        expr = f.ObjectAllValuesFrom("a:hasPet", "a:Dog")
        self.assertEqual("ObjectAllValuesFrom( a:hasPet a:Dog )", expr.to_funowl())

        expr = f.ObjectHasValue("a:fatherOf", "a:Stewie")
        self.assertEqual("ObjectHasValue( a:fatherOf a:Stewie )", expr.to_funowl())

        expr = f.ObjectHasSelf("a:likes")
        self.assertEqual("ObjectHasSelf( a:likes )", expr.to_funowl())

    def test_object_cardinality(self):
        """Test object restrictions."""
        expr = f.ObjectMinCardinality(2, "a:fatherOf", "a:Man")
        self.assertEqual("ObjectMinCardinality( 2 a:fatherOf a:Man )", expr.to_funowl())

        expr = f.ObjectMaxCardinality(2, "a:hasPet")
        self.assertEqual("ObjectMaxCardinality( 2 a:hasPet )", expr.to_funowl())

        expr = f.ObjectExactCardinality(1, "a:hasPet", "a:Dog")
        self.assertEqual("ObjectExactCardinality( 1 a:hasPet a:Dog )", expr.to_funowl())

    def test_data_restrictions(self):
        """Test object restrictions."""
        expr = f.DataSomeValuesFrom(
            ["a:hasAge"],
            f.DatatypeRestriction("xsd:integer", [("xsd:maxExclusive", term.Literal(20))]),
        )
        self.assertEqual(
            'DataSomeValuesFrom( a:hasAge DatatypeRestriction( xsd:integer xsd:maxExclusive "20"^^xsd:integer ) )',
            expr.to_funowl(),
        )

        expr = f.DataAllValuesFrom(["a:hasZIP"], "xsd:integer")
        self.assertEqual("DataAllValuesFrom( a:hasZIP xsd:integer )", expr.to_funowl())

        expr = f.DataHasValue("a:hasAge", term.Literal(17))
        self.assertEqual('DataHasValue( a:hasAge "17"^^xsd:integer )', expr.to_funowl())

    def test_data_cardinality(self):
        """Test outputting data cardinality constraints."""
        r = "rdfs:label"

        expr = f.DataExactCardinality(1, r)
        self.assertEqual("DataExactCardinality( 1 rdfs:label )", expr.to_funowl())

        expr = f.DataMinCardinality(1, r)
        self.assertEqual("DataMinCardinality( 1 rdfs:label )", expr.to_funowl())

        expr = f.DataMaxCardinality(5, r)
        self.assertEqual("DataMaxCardinality( 5 rdfs:label )", expr.to_funowl())


class TestSection9Axioms(unittest.TestCase):
    """Test Section 9: Axioms."""

    def test_subclass_of(self):
        expr = f.SubClassOf("a:Baby", "a:Child")
        self.assertEqual("SubClassOf( a:Baby a:Child )", expr.to_funowl())

        expr = f.SubClassOf(f.ObjectSomeValuesFrom("a:hasChild", "a:Child"), "a:Parent")
        self.assertEqual(
            "SubClassOf( ObjectSomeValuesFrom( a:hasChild a:Child ) a:Parent )", expr.to_funowl()
        )

    def test_equivalent_classes(self):
        """Test equivalent class axioms."""
        expr = f.EquivalentClasses(["a:Boy", f.ObjectIntersectionOf(["a:Child", "a:Man"])])
        self.assertEqual(
            "EquivalentClasses( a:Boy ObjectIntersectionOf( a:Child a:Man ) )", expr.to_funowl()
        )

    def test_disjoint_classes(self):
        """Test disjoint class axioms."""
        expr = f.EquivalentClasses(["a:Boy", "a:Girl"])
        self.assertEqual("EquivalentClasses( a:Boy a:Girl )", expr.to_funowl())

    def test_disjoint_union(self):
        """Test disjoint union axioms."""
        expr = f.DisjointUnion("a:Child", ["a:Boy", "a:Girl"])
        self.assertEqual("DisjointUnion( a:Child a:Boy a:Girl )", expr.to_funowl())

    def test_subproperties(self) -> None:
        """Test object sub-property."""
        expr = f.SubObjectPropertyOf("a:hasDog", "a:hasPet")
        self.assertEqual("SubObjectPropertyOf( a:hasDog a:hasPet )", expr.to_funowl())


class TestSection10(unittest.TestCase):
    def test_annotation_assertion(self):
        """Test AnnotationAssertion."""
        expected = 'AnnotationAssertion( rdfs:label a:Person "Represents the set of all people." )'
        expr = f.AnnotationAssertion(
            "rdfs:label", "a:Person", f.LiteralBox("Represents the set of all people.")
        )
        self.assertEqual(expected, expr.to_funowl())

        expected = 'AnnotationAssertion( Annotation( dc:terms orcid:0000-0003-4423-4370 ) rdfs:label a:Person "Represents the set of all people." )'
        expr = f.AnnotationAssertion(
            "rdfs:label",
            "a:Person",
            f.LiteralBox("Represents the set of all people."),
            annotations=[f.Annotation("dc:terms", "orcid:0000-0003-4423-4370")],
        )
        self.assertEqual(expected, expr.to_funowl())


class TestRDF(unittest.TestCase):
    """Test serialization to RDF."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the serialization test case."""
        cls.axiom_examples: list[f.Axiom] = [
            f.SubClassOf("owl:Thing", f.DataMaxCardinality(1, "a:hasAge")),
            f.SubClassOf("a:Dog", "a:Pet"),
            f.SubClassOf("a:Dog", "owl:Thing"),
            f.SubObjectPropertyOf("a:hasDog", "a:hasPet"),
            f.SubObjectPropertyOf(
                "a:hasDog",
                "a:hasPet",
                annotations=[f.Annotation("dcterms:contributor", "orcid:0000-0003-4423-4370")],
            ),
            f.AnnotationAssertion("rdfs:label", "a:Dog", f.l("dog")),
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
            f.DifferentIndividuals(["a:Peter", "a:Peter_Griffin"]),
            f.EquivalentClasses(
                [
                    "a:GriffinFamilyMember",
                    f.ObjectOneOf("a:Peter a:Lois a:Stewie a:Meg a:Chris a:Brian".split()),
                ]
            ),
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
            f.SubDataPropertyOf("a:hasLastName", "a:hasName"),
            f.SubAnnotationPropertyOf("a:brandName", "a:synonymType"),
            f.ObjectPropertyAssertion("a:parentOf", "a:Peter", "a:Chris"),
            f.NegativeDataPropertyAssertion("a:hasAge", "a:Meg", 5),
            f.NegativeObjectPropertyAssertion("a:hasSon", "a:Peter", "a:Meg"),
            f.DisjointDataProperties(["a:hasName", "a:hasAddress"]),
            f.DisjointObjectProperties(["a:hasFather", "a:hasMother"]),
            f.HasKey("owl:Thing", [], ["a:hasSSN"]),
            f.SubObjectPropertyOf(
                f.ObjectPropertyChain(["a:hasMother", "a:hasSister"]), "a:hasAunt"
            ),
        ]

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

    def test_rdf(self) -> None:
        """Test serialization to RDF."""
        for axiom in self.axiom_examples:
            with self.subTest(axiom=axiom.to_funowl()):
                try:
                    a = f._get_rdf_graph(axiom, prefix_map=f.EXAMPLE_PREFIX_MAP)
                except NotImplementedError:
                    a = rdflib.Graph()
                b = f._get_rdf_graph_oracle(axiom, prefix_map=f.EXAMPLE_PREFIX_MAP)
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


def dump_nt_sorted(g: Graph) -> str:
    """Write all triples in a canonical way."""
    return "\n".join(line for line in sorted(g.serialize(format="nt").splitlines()) if line)


def _get_all_axiom_types() -> set[type[f.Axiom]]:
    rv: set[type[f.Axiom]] = set()
    for x in dir(f):
        if x.startswith("_"):
            continue
        t = getattr(f, x)
        if isinstance(t, type) and issubclass(t, f.Axiom):
            rv.add(t)
    return rv
