"""Test reading typedefs."""

import unittest

from pyobo import Obo, Reference, TypeDef, default_reference
from pyobo.struct import part_of
from pyobo.struct.obo import from_str
from pyobo.struct.reference import OBOLiteral
from pyobo.struct.typedef import is_conjugate_base_of, occurs_in, see_also
from pyobo.struct.vocabulary import CHARLIE, has_contributor

REASON_OBONET_IMPL = (
    "This needs to be fixed upstream, since obonet's parser "
    "for synonyms fails on the open squiggly bracket {"
)


class TestReaderTypedef(unittest.TestCase):
    """Tests for typedefs."""

    def get_only_typedef(self, ontology: Obo) -> TypeDef:
        """Assert there is only a single typedef in the ontology and return it."""
        self.assertEqual(1, len(ontology.typedefs))
        return ontology.typedefs[0]

    def assert_boolean_tag(self, tag: str) -> None:
        """Assert the boolean flag works right."""
        ontology = from_str(f"""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            {tag}: true
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertTrue(hasattr(typedef, tag))
        value = getattr(typedef, tag)
        self.assertIsNotNone(value)
        self.assertTrue(value)

        ontology = from_str(f"""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            {tag}: false
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertTrue(hasattr(typedef, tag))
        value = getattr(typedef, tag)
        self.assertIsNotNone(value)
        self.assertFalse(value)

    def test_1_missing_identifier(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        with self.assertRaises(KeyError) as exc:
            from_str("""\
                ontology: chebi

                [Typedef]
                name: nope
            """)
        self.assertEqual("typedef is missing an `id`", exc.exception.args[0])

    def test_2_is_anonymous(self) -> None:
        """Test the ``is_anonymous`` tag."""
        self.assert_boolean_tag("is_anonymous")

    def test_3_name(self) -> None:
        """Test the name tag."""
        ontology = from_str("""\
            ontology: chebi

            [Typedef]
            id: CHEBI:1234
            name: test
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual("test", typedef.name)

    def test_4_namespace(self) -> None:
        """Test the ``namespace`` tag."""
        ontology = from_str("""\
            ontology: RO

            [Typedef]
            id: RO:1234567
            namespace: test-namespace
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual("test-namespace", typedef.namespace)

    def test_5_alt_id(self) -> None:
        """Test the ``alt_id`` tag."""
        ontology = from_str("""\
            ontology: RO

            [Typedef]
            id: RO:1234567
            alt_id: RO:2222222
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [Reference(prefix="RO", identifier="2222222")],
            list(typedef.alt_ids),
        )

    def test_7_comment(self) -> None:
        """Test the ``subset`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: RO:1234567
            comment: comment
        """)
        self.get_only_typedef(ontology)

    def test_8_subset(self) -> None:
        """Test the ``subset`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: RO:1234567
            subset: test-subset
        """)
        term = self.get_only_typedef(ontology)
        self.assertEqual([default_reference("ro", "test-subset")], term.subsets)

    def test_10_typedef_xref(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        ontology = from_str("""\
            ontology: chebi

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
            xref: debio:0000010
        """)
        self.assertEqual(1, len(ontology.typedefs))
        self.assertEqual(is_conjugate_base_of.pair, ontology.typedefs[0].pair)

    def test_11_property_value(self) -> None:
        """Test the ``property_value`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: RO:0018033
            property_value: dcterms:contributor orcid:0000-0003-4423-4370 ! contributor Charles Tapley Hoyt
            property_value: debio:0000020 "abc" xsd:string
        """)
        td1 = Reference(prefix="debio", identifier="0000020")
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(2, len(typedef.properties))
        self.assertIn(has_contributor, typedef.properties)
        self.assertEqual([CHARLIE], typedef.properties[has_contributor])
        self.assertIn(td1, typedef.properties)
        self.assertEqual(1, len(typedef.properties[td1]))
        self.assertEqual(OBOLiteral.string("abc"), typedef.properties[td1][0])

    def test_12_domain(self) -> None:
        """Test the ``domain`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            domain: BFO:0000003 ! occurrent
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertIsNotNone(typedef.domain)
        self.assertEqual(Reference.from_curie("BFO:0000003"), typedef.domain)

    def test_13_range(self) -> None:
        """Test the ``range`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            range: BFO:0000004
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertIsNotNone(typedef.range)
        self.assertEqual(Reference.from_curie("BFO:0000004"), typedef.range)

    def test_14_builtin(self) -> None:
        """Test the builtin tag."""
        self.assert_boolean_tag("builtin")

    def test_15_holds_over_chain(self) -> None:
        """Test the ``holds_over_chain`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            name: occurs in
            holds_over_chain: BFO:0000050 BFO:0000066 ! part of occurs in
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [
                [
                    part_of.reference,
                    occurs_in.reference,
                ]
            ],
            typedef.holds_over_chain,
        )

    def test_16_is_anti_symmetric(self) -> None:
        """Test the ``is_anti_symmetric`` tag."""
        self.assert_boolean_tag("is_anti_symmetric")

    def test_17_is_cyclic(self) -> None:
        """Test the ``is_cyclic`` tag."""
        self.assert_boolean_tag("is_cyclic")

    def test_18_is_reflexive(self) -> None:
        """Test the ``is_reflexive`` tag."""
        self.assert_boolean_tag("is_reflexive")

    def test_19_is_symmetric(self) -> None:
        """Test the ``is_symmetric`` tag."""
        self.assert_boolean_tag("is_symmetric")

    def test_20_is_transitive(self) -> None:
        """Test the ``is_transitive`` tag."""
        self.assert_boolean_tag("is_transitive")

    def test_21_is_functional(self) -> None:
        """Test the ``is_functional`` tag."""
        self.assert_boolean_tag("is_functional")

    def test_22_is_inverse_functional(self) -> None:
        """Test the ``is_inverse_functional`` tag."""
        self.assert_boolean_tag("is_inverse_functional")

    def test_23_is_a(self) -> None:
        """Test the ``is_a`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000050
            name: part of
            is_a: RO:0002131 ! overlaps
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(1, len(typedef.parents))
        self.assertEqual(Reference(prefix="RO", identifier="0002131"), typedef.parents[0])

    def test_24_intersection_of(self) -> None:
        """Test the ``intersection_of`` tag."""
        ontology = from_str("""\
            ontology: go

            [Typedef]
            id: GO:0000085
            name: G2 phase of mitotic cell cycle
            intersection_of: GO:0051319 ! G2 phase
            intersection_of: BFO:0000050 GO:0000278 ! part of mitotic cell cycle
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(2, len(typedef.intersection_of))
        self.assertEqual(
            [
                Reference.from_curie("GO:0051319"),
                (Reference.from_curie("BFO:0000050"), Reference.from_curie("GO:0000278")),
            ],
            typedef.intersection_of,
        )

    def test_25_union_of(self) -> None:
        """Test the ``union_of`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: GO:0000001
            union_of: GO:0000002
            union_of: GO:0000003
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(2, len(typedef.union_of))
        self.assertEqual(
            [
                Reference(prefix="GO", identifier="0000002"),
                Reference(prefix="GO", identifier="0000003"),
            ],
            typedef.union_of,
        )

    def test_26_equivalent_to(self) -> None:
        """Test the ``equivalent_to`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: GO:0000001
            equivalent_to: GO:0000002
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual([Reference(prefix="GO", identifier="0000002")], typedef.equivalent_to)

    def test_27_disjoint_from(self) -> None:
        """Test the ``disjoint_from`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            disjoint_from: RO:1111111
            disjoint_from: RO:2222222
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [
                Reference(prefix="RO", identifier="1111111"),
                Reference(prefix="RO", identifier="2222222"),
            ],
            typedef.disjoint_from,
        )

    def test_28_inverse_of(self) -> None:
        """Test the ``inverse_of`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            inverse_of: BFO:0000067 ! contains process
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(Reference(prefix="BFO", identifier="0000067"), typedef.inverse)

    def test_29_transitive_over(self) -> None:
        """Test the ``transitive_over`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            transitive_over: BFO:0000050 ! part of
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [Reference(prefix="BFO", identifier="0000050", name="part of")], typedef.transitive_over
        )

    def test_30_equivalent_to_chain(self) -> None:
        """Test the ``equivalent_to_chain`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: GO:1111111
            equivalent_to_chain: GO:2222222 GO:3333333
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [
                [
                    Reference(prefix="GO", identifier="2222222"),
                    Reference(prefix="GO", identifier="3333333"),
                ]
            ],
            typedef.equivalent_to_chain,
        )

    def test_31_disjoint_over(self) -> None:
        """Test the ``disjoint_over`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            disjoint_over: RO:1111111
            disjoint_over: RO:2222222
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(
            [
                Reference(prefix="RO", identifier="1111111"),
                Reference(prefix="RO", identifier="2222222"),
            ],
            typedef.disjoint_over,
        )

    def test_32_relationship(self) -> None:
        """Test the ``relationship`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            relationship: RO:1111111 RO:2222222
        """)
        typedef = self.get_only_typedef(ontology)
        r1 = Reference(prefix="RO", identifier="1111111")
        r2 = Reference(prefix="RO", identifier="2222222")
        self.assertIn(r1, typedef.relationships)
        self.assertEqual(1, len(typedef.relationships[r1]))
        self.assertEqual(r2, typedef.relationships[r1][0])

    def test_33_is_obsolete(self) -> None:
        """Test the ``is_obsolete`` tag."""
        self.assert_boolean_tag("is_obsolete")

    def test_34_created_by(self) -> None:
        """Test the ``created_by`` tag."""

    def test_35_creation_date(self) -> None:
        """Test the ``creation_date`` tag."""

    def test_36_replaced_by(self) -> None:
        """Test the ``replaced_by`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            replaced_by: RO:1111111
        """)
        r = self.get_only_typedef(ontology)
        self.assertEqual(
            [Reference(prefix="RO", identifier="1111111")],
            r.get_replaced_by(),
            msg=str(dict(r.properties)),
        )

    def test_37_consider(self) -> None:
        """Test the ``consider`` tag."""
        ontology = from_str("""\
            ontology: ro

            [Typedef]
            id: BFO:0000066
            consider: RO:1111111
        """)
        typedef = self.get_only_typedef(ontology)
        r = typedef.get_property_objects(see_also)
        self.assertEqual(1, len(r))
        self.assertEqual(Reference(prefix="RO", identifier="1111111"), r[0])

    def test_38_expand_assertion_to(self) -> None:
        """Test the ``expand_assertion_to`` tag."""

    def test_39_expand_expression_to(self) -> None:
        """Test the ``expand_expression_to`` tag."""

    def test_40_is_metadata_tag(self) -> None:
        """Test the ``is_metadata_tag`` tag."""
        self.assert_boolean_tag("is_metadata_tag")

    def test_41_is_class_level(self) -> None:
        """Test the ``is_class_level`` tag."""
        self.assert_boolean_tag("is_class_level")
