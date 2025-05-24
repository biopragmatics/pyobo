"""Test the reader on ontology metadata."""

import datetime
import unittest

from pyobo import Obo, Reference, SynonymTypeDef, Term, TypeDef, default_reference
from pyobo.struct import part_of
from pyobo.struct.obo import from_str
from pyobo.struct.reference import OBOLiteral
from pyobo.struct.struct_utils import Annotation
from pyobo.struct.typedef import comment, equivalent_class


class TestReaderOntologyMetadata(unittest.TestCase):
    """Test the reader on ontology metadata."""

    def get_only_term(self, ontology: Obo) -> Term:
        """Assert there is only a single term in the ontology and return it."""
        terms = list(ontology.iter_terms())
        self.assertEqual(1, len(terms))
        term = terms[0]
        return term

    def get_only_typedef(self, ontology: Obo) -> TypeDef:
        """Assert there is only a single typedef in the ontology and return it."""
        self.assertEqual(1, len(ontology.typedefs))
        return ontology.typedefs[0]

    def test_0_missing_date_version(self) -> None:
        """Test an ontology with a missing date and version."""
        ontology = from_str("""\
            ontology: chebi
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    # 1 format-version is unnecessary
    # 2 for data-version, see the full test case below

    def test_3_bad_date_format(self) -> None:
        """Test an ontology with a malformed date and no version."""
        ontology = from_str("""\
            ontology: chebi
            date: aabbccddeee
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    def test_3_date_no_version(self) -> None:
        """Test an ontology with a date but no version."""
        ontology = from_str("""\
            ontology: chebi
            date: 20:11:2024 18:44
        """)
        self.assertEqual(datetime.datetime(2024, 11, 20, 18, 44), ontology.date)
        self.assertEqual("2024-11-20", ontology.data_version)

    # 4 saved-by not necessary
    # 5 auto-generated-by

    def test_6_import(self) -> None:
        """Test the ``import`` tag."""
        ontology = from_str("""\
            ontology: go
            import: chebi
            import: http://purl.obolibrary.org/obo/envo.owl
        """)
        self.assertEqual(["chebi", "http://purl.obolibrary.org/obo/envo.owl"], ontology.imports)

    def test_7_subset(self) -> None:
        """Test parsing a subset definition."""
        ontology = from_str("""\
            ontology: chebi
            subsetdef: TEST "comment"
        """)
        self.assertEqual(
            [(default_reference("chebi", "TEST"), "comment")],
            ontology.subsetdefs,
        )

    def test_8_synonym_typedef(self) -> None:
        """Test the ``synonym_typedef`` tag."""
        with self.assertRaises(ValueError):
            # This raises
            from_str(
                """\
                ontology: chebi
                synonymtypedef: ST5 "ST5 Name" garbage
            """,
                strict=True,
            )

        ontology = from_str(
            """\
            ontology: chebi
            synonymtypedef: ST1 "ST1 Name" EXACT
            synonymtypedef: ST2 "ST2 Name" NARROW
            synonymtypedef: ST3 "ST3 Name"
            synonymtypedef: ST4 "ST4 Name" exact
            synonymtypedef: ST5 "ST5 Name" garbage
            synonymtypedef: OMO:0000001 "E1 Name" EXACT
            synonymtypedef: OMO:0000002 "E2 Name" NARROW
            synonymtypedef: OMO:0000003 "E3 Name"
        """,
            strict=False,
        )
        self.assertEqual(
            [
                SynonymTypeDef(
                    reference=default_reference("chebi", "ST1", name="ST1 Name"),
                    specificity="EXACT",
                ),
                SynonymTypeDef(
                    reference=default_reference("chebi", "ST2", name="ST2 Name"),
                    specificity="NARROW",
                ),
                SynonymTypeDef(
                    reference=default_reference("chebi", "ST3", name="ST3 Name"), specificity=None
                ),
                SynonymTypeDef(
                    reference=default_reference("chebi", "ST4", name="ST4 Name"),
                    specificity="EXACT",
                ),
                SynonymTypeDef(
                    reference=default_reference("chebi", "ST5", name="ST5 Name"), specificity=None
                ),
                SynonymTypeDef(
                    reference=Reference(prefix="OMO", identifier="0000001", name="E1 Name"),
                    specificity="EXACT",
                ),
                SynonymTypeDef(
                    reference=Reference(prefix="OMO", identifier="0000002", name="E2 Name"),
                    specificity="NARROW",
                ),
                SynonymTypeDef(
                    reference=Reference(prefix="OMO", identifier="0000003", name="E3 Name"),
                    specificity=None,
                ),
            ],
            ontology.synonym_typedefs,
        )

    # TODO default-namespace
    # TODO namespace-id-rule

    def test_11_idspace(self) -> None:
        """Test the ``idspace`` tag."""
        ontology = from_str("""\
            ontology: go
            idspace: hgnc https://bioregistry.io/hgnc:
            idspace: ex https://example.org/ "example"
        """)
        self.assertEqual(
            {
                "hgnc": "https://bioregistry.io/hgnc:",
                "ex": "https://example.org/",
            },
            ontology.idspaces,
        )

    def test_12_xref_equivalent(self) -> None:
        """Test the ``treat-xrefs-as-equivalent`` macro."""
        ontology = from_str("""\
            ontology: go
            treat-xrefs-as-equivalent: CL

            [Term]
            id: GO:0005623
            name: cell
            xref: CL:0000000
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.xrefs))
        self.assertEqual(0, len(term.parents))
        self.assertEqual(0, len(term.properties))
        self.assertEqual(1, len(term.relationships))
        self.assertEqual(0, len(term.intersection_of))
        self.assertIn(equivalent_class.reference, term.relationships)
        self.assertEqual(
            [Reference(prefix="CL", identifier="0000000")],
            term.relationships[equivalent_class.reference],
        )

    def test_13_xref_genus_differentia(self) -> None:
        """Test the ``treat-xrefs-as-is_a `` macro.

        The test should become the same as

        .. code-block::

            [Term]
            id: ZFA:0000134
            intersection_of: CL:0000540
            intersection_of: BFO:0000050 NCBITaxon:7955
        """
        ontology = from_str("""\
              ontology: zfa
              treat-xrefs-as-genus-differentia: CL BFO:0000050 NCBITaxon:7955

              [Term]
              id: ZFA:0000134
              xref: CL:0000540
          """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.xrefs))
        self.assertEqual(0, len(term.parents))
        self.assertEqual(0, len(term.properties))
        self.assertEqual(0, len(term.relationships))
        self.assertEqual(2, len(term.intersection_of))
        self.assertEqual(
            [
                Reference(prefix="CL", identifier="0000540"),
                Annotation(part_of.reference, Reference(prefix="NCBITaxon", identifier="7955")),
            ],
            term.intersection_of,
        )

    def test_14_xref_relation(self) -> None:
        """Test the ``treat-xrefs-as-relationship`` macro."""
        ontology = from_str("""\
            ontology: go
            treat-xrefs-as-relationship: CL BFO:0000000

            [Term]
            id: GO:0005623
            name: cell
            xref: CL:0000000
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.xrefs))
        self.assertEqual(0, len(term.parents))
        self.assertEqual(0, len(term.properties))
        self.assertEqual(1, len(term.relationships))
        self.assertEqual(0, len(term.intersection_of))
        pred = Reference(prefix="BFO", identifier="0000000")
        self.assertIn(pred, term.relationships)
        self.assertEqual([Reference(prefix="CL", identifier="0000000")], term.relationships[pred])

    def test_15_xref_is_a_for_term(self) -> None:
        """Test the ``treat-xrefs-as-is_a`` macro."""
        ontology = from_str("""\
            ontology: go
            treat-xrefs-as-is_a: CL

            [Term]
            id: GO:0005623
            name: cell
            xref: CL:0000000
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.xrefs), msg=term.xrefs)
        self.assertEqual(1, len(term.parents))
        self.assertEqual(0, len(term.properties))
        self.assertEqual(0, len(term.relationships))
        self.assertEqual(0, len(term.intersection_of))
        self.assertEqual([Reference(prefix="CL", identifier="0000000")], term.parents)

    def test_15_xref_is_a_for_typedef(self) -> None:
        """Test the ``treat-xrefs-as-is_a`` macro."""
        ontology = from_str("""\
            ontology: ro
            treat-xrefs-as-is_a: skos

            [Typedef]
            id: RO:0000000
            xref: skos:closeMatch
        """)
        typedef = self.get_only_typedef(ontology)
        self.assertEqual(0, len(typedef.xrefs), msg=typedef.xrefs)
        self.assertEqual(0, len(typedef.relationships))
        self.assertEqual(0, len(typedef.intersection_of))
        self.assertEqual(1, len(typedef.parents))
        self.assertEqual([Reference(prefix="skos", identifier="closeMatch")], typedef.parents)

    def test_16_remark(self) -> None:
        """Test the ``remark`` tag."""
        ontology = from_str("""\
            ontology: ro
            remark: hello 1
            remark: hello 2
        """)
        self.assertEqual(
            [
                Annotation(comment.reference, OBOLiteral.string("hello 1")),
                Annotation(comment.reference, OBOLiteral.string("hello 2")),
            ],
            ontology.property_values,
        )

    def test_17_unknown_ontology_prefix(self) -> None:
        """Test an ontology with an unknown prefix."""
        with self.assertRaises(ValueError) as exc:
            from_str("""\
                ontology: nope
            """)
        self.assertEqual("unknown prefix: nope", exc.exception.args[0])

    def test_18_properties(self) -> None:
        """Test parsing properties."""
        ontology = from_str("""\
            ontology: chebi
            property_value: heyo also_heyo
        """)
        self.assertEqual(
            [(default_reference("chebi", "heyo"), default_reference("chebi", "also_heyo"))],
            ontology.property_values,
        )

    def test_18_root(self) -> None:
        """Test root terms."""
        ontology = from_str("""\
            ontology: go
            property_value: IAO:0000700 GO:0050069

            [Term]
            id: GO:0050069
        """)
        # FIXME support default reference, like property_value: IAO:0000700 adhoc
        self.assertEqual(
            [Reference(prefix="GO", identifier="0050069")],
            ontology.root_terms,
        )

    def test_18_root_with_url(self) -> None:
        """Test root terms as URL."""
        ontology = from_str("""\
            ontology: lepao
            property_value: IAO:0000700 http://purl.obolibrary.org/obo/LEPAO_0000006
        """)
        self.assertEqual(
            [Reference(prefix="LEPAO", identifier="0000006")],
            ontology.root_terms,
        )

    def test_18_root_with_url_quoted(self) -> None:
        """Test root terms as URL."""
        ontology = from_str("""\
            ontology: lepao
            property_value: IAO:0000700 "http://purl.obolibrary.org/obo/LEPAO_0000006"
        """)
        self.assertEqual(
            [Reference(prefix="LEPAO", identifier="0000006")],
            ontology.root_terms,
        )

    def test_18_root_with_typed_uri(self) -> None:
        """Test root terms as URL."""
        ontology = from_str("""\
            ontology: lepao
            property_value: IAO:0000700 "http://purl.obolibrary.org/obo/LEPAO_0000006" xsd:anyURI
        """)
        self.assertEqual(
            [Reference(prefix="LEPAO", identifier="0000006")],
            ontology.root_terms,
        )

    def test_18_root_with_mistyped_uri(self) -> None:
        """Test root terms as URL."""
        ontology = from_str("""\
            ontology: lepao
            property_value: IAO:0000700 "http://purl.obolibrary.org/obo/LEPAO_0000006" xsd:string
        """)
        self.assertEqual(
            [Reference(prefix="LEPAO", identifier="0000006")],
            ontology.root_terms,
        )


class TestVersionHandling(unittest.TestCase):
    """Test version handling."""

    def test_no_version_no_data(self):
        """Test when nothing is given."""
        ontology = from_str("""\
            ontology: chebi
        """)
        self.assertIsNone(ontology.data_version)

    def test_static_rewrite(self):
        """Test using custom configuration for version lookup."""
        ontology = from_str("""\
            ontology: orth
        """)
        self.assertEqual("2", ontology.data_version, msg="The static rewrite wasn't applied")

    def test_simple_version(self):
        """Test handling a simple version."""
        ontology = from_str("""\
            ontology: chebi
            data-version: 123
        """)
        self.assertEqual("123", ontology.data_version)

    def test_releases_prefix_simple(self):
        """Test a parsing a simple version starting with ``releases/``."""
        ontology = from_str("""\
            ontology: chebi
            data-version: releases/123
        """)
        self.assertEqual(
            "123",
            ontology.data_version,
            msg="The prefix ``releases/`` wasn't properly automatically stripped",
        )

    def test_releases_prefix_complex(self):
        """Test parsing a complex string starting with ``releases/``."""
        ontology = from_str("""\
            ontology: chebi
            data-version: releases/123/chebi.owl
        """)
        self.assertEqual(
            "123",
            ontology.data_version,
            msg="The prefix ``releases/`` wasn't properly automatically stripped",
        )

    def test_no_version_with_date(self):
        """Test when the date is substituted for a missing version."""
        ontology = from_str("""\
            ontology: chebi
            date: 20:11:2024 18:44
        """)
        self.assertEqual("2024-11-20", ontology.data_version)

    def test_bad_version(self):
        """Test that a version with slashes raises an error."""
        with self.assertRaises(ValueError):
            from_str("""\
                ontology: chebi
                data-version: /////
            """)

    def test_data_prefix_strip(self):
        """Test when a prefix gets stripped from the beginning of a version."""
        ontology = from_str("""\
            ontology: sasap
            data-version: http://purl.dataone.org/odo/SASAP/0.3.1
        """)
        self.assertEqual(
            "0.3.1", ontology.data_version, msg="The custom defined prefix wasn't stripped"
        )

    def test_version_full_rewrite(self):
        """Test when a version gets fully replaced from a custom configuration."""
        ontology = from_str("""\
            ontology: owl
            data-version: $Date: 2009/11/15 10:54:12 $
        """)
        self.assertEqual(
            "2009-11-15", ontology.data_version, msg="The custom rewrite wasn't invooked"
        )

    def test_version_injected(self):
        """Test when a missing version gets overwritten."""
        ontology = from_str(
            """\
            ontology: chebi
        """,
            version="123",
        )
        self.assertEqual("123", ontology.data_version)

    def test_version_overwrite_mismatch(self):
        """Test when a version gets overwritten, but it's not matching."""
        ontology = from_str(
            """\
            ontology: chebi
            data-version: 122
        """,
            version="123",
        )
        self.assertEqual("123", ontology.data_version)
