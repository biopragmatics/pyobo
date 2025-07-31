"""Tests for the reader."""

import unittest

from pyobo import Obo, Reference, Term
from pyobo.identifier_utils import NotCURIEError, UnparsableIRIError, UnregisteredPrefixError
from pyobo.struct import TypeDef, default_reference
from pyobo.struct import vocabulary as v
from pyobo.struct.obo.reader import from_str, get_first_nonescaped_quote
from pyobo.struct.reference import OBOLiteral
from pyobo.struct.struct import abbreviation
from pyobo.struct.struct_utils import Annotation
from pyobo.struct.typedef import (
    comment,
    definition_source,
    derives_from,
    exact_match,
    has_dbxref,
    is_conjugate_base_of,
    see_also,
    term_replaced_by,
)
from pyobo.struct.vocabulary import CHARLIE

REASON_OBONET_IMPL = (
    "This needs to be fixed upstream, since obonet's parser "
    "for synonyms fails on the open squiggly bracket {"
)


class TestUtils(unittest.TestCase):
    """Test utilities for the reader."""

    def test_first_nonescaped_quote(self):
        """Test finding the first non-escaped double quote."""
        self.assertIsNone(get_first_nonescaped_quote(""))
        self.assertEqual(0, get_first_nonescaped_quote('"'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc"'))
        self.assertEqual(2, get_first_nonescaped_quote('\\""'))
        self.assertEqual(3, get_first_nonescaped_quote('abc"'))
        self.assertEqual(3, get_first_nonescaped_quote('abc""'))
        self.assertIsNone(get_first_nonescaped_quote("abc"))
        self.assertIsNone(get_first_nonescaped_quote('abc\\"'))
        self.assertIsNone(get_first_nonescaped_quote('\\"hello\\"'))


class TestReaderTerm(unittest.TestCase):
    """Test the reader."""

    def get_only_term(self, ontology: Obo) -> Term:
        """Assert there is only a single term in the ontology and return it."""
        terms = list(ontology.iter_terms())
        self.assertNotEqual(0, len(terms), msg="was not able to parse the only term")
        self.assertEqual(
            1, len(terms), msg="got too many terms:\n\n{}".format("\n".join(str(t) for t in terms))
        )
        term = terms[0]
        return term

    def assert_boolean_flag(self, tag: str) -> None:
        """Test a boolean flag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: test
        """)
        term = self.get_only_term(ontology)
        self.assertTrue(hasattr(term, tag))
        value = getattr(term, tag)
        self.assertIsNone(value)

        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            {tag}: true
        """)
        term = self.get_only_term(ontology)
        self.assertTrue(hasattr(term, tag))
        value = getattr(term, tag)
        self.assertIsNotNone(value)
        self.assertTrue(value)

        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            {tag}: false
        """)
        term = self.get_only_term(ontology)
        self.assertTrue(hasattr(term, tag))
        value = getattr(term, tag)
        self.assertIsNotNone(value)
        self.assertFalse(value)

    def test_0_minimal(self) -> None:
        """Test an ontology with a version but no date."""
        ontology = from_str("""\
            data-version: 185
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            def: "Test definition" [orcid:1234-1234-1234-1234]
            xref: drugbank:DB12345
        """)
        self.assertEqual([], ontology.typedefs)
        self.assertEqual([], ontology.synonym_typedefs)

        term = self.get_only_term(ontology)
        self.assertEqual("Test definition", term.definition)
        self.assertEqual(1, len(term.xrefs))
        xref = term.xrefs[0]
        self.assertEqual("drugbank:DB12345", xref.curie)

    def test_1_node_unparsable(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        text = """\
            ontology: chebi

            [Term]
            id: nope:1234
        """
        with self.assertRaises(UnregisteredPrefixError):
            from_str(text, strict=True)
        ontology = from_str(text, strict=False)
        self.assertEqual(0, len(list(ontology.iter_terms())))

    def test_2_is_anonymous(self) -> None:
        """Test the ``is-anonymous`` tag."""
        self.assert_boolean_flag("is_anonymous")

    def test_3_name(self) -> None:
        """Test the ``name`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: test-name
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("test-name", term.name)

    def test_4_namespace(self) -> None:
        """Test the ``namespacae`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            namespace: test-namespace
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("test-namespace", term.namespace)

    def test_5_alt_id(self) -> None:
        """Test the ``alt_id`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            alt_id: CHEBI:1
            alt_id: CHEBI:2
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(2, len(term.alt_ids))
        self.assertEqual(
            [
                Reference(prefix="CHEBI", identifier="1"),
                Reference(prefix="CHEBI", identifier="2"),
            ],
            list(term.alt_ids),
        )

    def test_6_definition_missing_start_quote(self) -> None:
        """Test parsing a definition missing a starting quote."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: malformed definition without quotes
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.definition)

    def test_6_definition_missing_end_quote(self) -> None:
        """Test parsing a definition missing an ending quote."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "malformed definition without quotes
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.definition)

    def test_6_definition_no_provenance(self) -> None:
        """Test parsing a term with a definition and no provenance brackets."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)

    def test_6_definition_empty_provenance(self) -> None:
        """Test parsing a term with a definition and empty provenance."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234" []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)

    def test_6_definition_with_provenance_object(self) -> None:
        """Test parsing a term with a definition and provenance."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234" [{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)
        self.assertEqual(1, len(term.provenance))
        self.assertEqual(CHARLIE, term.provenance[0])

    def test_6_definition_with_provenance_object_with_comment(self) -> None:
        """Test parsing a term with a definition and provenance, with a comment."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234" [{CHARLIE.curie} "TestComment"]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)
        self.assertEqual(1, len(term.provenance))
        self.assertEqual(CHARLIE, term.provenance[0])

    def test_6_definition_with_provenance_uri(self) -> None:
        """Test parsing a term with a definition and provenance."""
        ontology = from_str("""\
               ontology: chebi

               [Term]
               id: CHEBI:1234
               def: "definition of CHEBI:1234" [https://example.org/test]
           """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)
        annotations = term._get_annotations(v.has_description, "definition of CHEBI:1234")
        self.assertEqual(
            1, len(annotations), msg=f"Wrong annotations, see all axioms:\n\n{dict(term._axioms)}"
        )
        annotation = annotations[0]
        self.assertEqual(has_dbxref.pair, annotation.predicate.pair)
        self.assertIsInstance(annotation.value, OBOLiteral)
        self.assertEqual(OBOLiteral.uri("https://example.org/test"), annotation.value)

        self.assertEqual(1, len(term.provenance))
        self.assertEqual(OBOLiteral.uri("https://example.org/test"), term.provenance[0])

    def test_6_provenance_no_definition(self) -> None:
        """Test parsing a term with provenance but no definition."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "" [{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.definition)
        self.assertEqual(0, len(term.provenance))

    def test_7_comment(self) -> None:
        """Test parsing a definition missing a starting quote."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            comment: comment
        """)
        term = self.get_only_term(ontology)
        comments = term.get_property_values(comment)
        self.assertEqual(1, len(comments))
        self.assertIsInstance(comments[0], OBOLiteral)
        self.assertEqual("comment", comments[0].value)

    def test_8_subset(self) -> None:
        """Test parsing subsets."""
        ontology = from_str("""\
            ontology: go

            [Term]
            id: GO:0050069
            subset: TESTSET
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.subsets))
        self.assertEqual(default_reference("go", "TESTSET"), term.subsets[0])

    def test_9_synonym_minimal(self) -> None:
        """Test parsing a synonym just the text."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertIsNone(synonym.specificity)
        self.assertIsNone(synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_with_specificity(self) -> None:
        """Test parsing a synonym with specificity."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" NARROW
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("NARROW", synonym.specificity)
        self.assertIsNone(synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_with_type_missing_def(self) -> None:
        """Test parsing a synonym with type, but missing type def."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" OMO:1234567
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        #  this is because no typedef existed
        self.assertIsNone(synonym.type)

    def test_9_synonym_with_type(self) -> None:
        """Test parsing a synonym with type."""
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" OMO:1234567
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertIsNone(synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_with_type_and_specificity(self) -> None:
        """Test parsing a synonym with specificity and type."""
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" NARROW OMO:1234567
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("NARROW", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_with_empty_prov(self) -> None:
        """Test parsing a synonym with specificity,type, and explicit empty provenance."""
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" NARROW OMO:1234567 []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("NARROW", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_with_provenance_uri(self) -> None:
        """Test parsing a synonym with specificity,type, and explicit empty provenance."""
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" NARROW OMO:1234567 [https://example.org/test]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("NARROW", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual([OBOLiteral.uri("https://example.org/test")], synonym.provenance)

    def test_9_synonym_no_type(self) -> None:
        """Test parsing a synonym with specificity and provenance."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" EXACT [Orphanet:93938,{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertIsNone(synonym.type)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )

    def test_9_synonym_full(self) -> None:
        """Test parsing a synonym with specificity, type, and provenance."""
        ontology = from_str(f"""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" EXACT OMO:1234567 [Orphanet:93938,{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )

    def test_9_synonym_dashed(self) -> None:
        """Test parsing a synonym with specificity, type, and provenance."""
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "Brown-Pearce tumour" EXACT OMO:0003005 []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("Brown-Pearce tumour", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="0003005"), synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_9_synonym_url(self) -> None:
        """Test parsing a synonym defined with a PURL."""
        ontology = from_str(f"""\
            ontology: chebi
            synonymtypedef: http://purl.obolibrary.org/obo/OMO_1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" EXACT OMO:1234567 [Orphanet:93938,{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )

    def test_9_synonym_casing(self) -> None:
        """Test parsing a synonym when an alternate case is used."""
        ontology = from_str(f"""\
            ontology: chebi
            synonymtypedef: OMO:1234567 ""

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" EXACT omo:1234567 [Orphanet:93938,{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )

    def test_9_synonym_default(self) -> None:
        """Test parsing a synonym that has a built-in prefix."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "DoguAnadoluKirmizisi" EXACT most_common_name []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("DoguAnadoluKirmizisi", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertIsNone(synonym.type)

        # now, we define it properly
        ontology = from_str("""\
            ontology: chebi
            synonymtypedef: most_common_name "most common name"

            [Term]
            id: CHEBI:1234
            synonym: "DoguAnadoluKirmizisi" EXACT most_common_name []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("DoguAnadoluKirmizisi", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(default_reference("chebi", "most_common_name"), synonym.type)

    def test_9_synonym_builtin(self) -> None:
        """Test parsing a synonym with specificity, type, and provenance."""
        text = """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "COP" EXACT ABBREVIATION []
        """

        ontology = from_str(text, upgrade=False)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("COP", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertIsNone(synonym.type)

        ontology = from_str(text, upgrade=True)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("COP", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(abbreviation.reference, synonym.type)

    @unittest.skip(reason=REASON_OBONET_IMPL)
    def test_9_synonym_with_annotations(self) -> None:
        """Test parsing a synonym with annotations."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "10*3.{copies}/mL" EXACT [] {http://purl.obolibrary.org/obo/NCIT_P383="AB", http://purl.obolibrary.org/obo/NCIT_P384="UCUM"}
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("10*3.{copies}/mL", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertIsNone(synonym.type)
        self.assertEqual([], synonym.provenance)
        # TODO update this when adding annotation parsing!
        self.assertEqual([], synonym.annotations)

    def test_10_xrefs(self) -> None:
        """Test getting mappings."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            xref: cas:389-08-2
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            {(has_dbxref.pair, Reference(prefix="cas", identifier="389-08-2").pair)},
            {(a.pair, b.pair) for a, b in term.get_mappings(include_xrefs=True)},
        )
        self.assertEqual(
            set(),
            {(a.pair, b.pair) for a, b in term.get_mappings(include_xrefs=False)},
        )

        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            xref: cas:389-08-2
            property_value: skos:exactMatch drugbank:DB00779
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            {(exact_match.pair, Reference(prefix="drugbank", identifier="DB00779").pair)},
            {(a.pair, b.pair) for a, b in term.get_mappings(include_xrefs=False)},
        )
        self.assertEqual(
            {
                (exact_match.pair, Reference(prefix="drugbank", identifier="DB00779").pair),
                (has_dbxref.pair, Reference(prefix="cas", identifier="389-08-2").pair),
            },
            {(a.pair, b.pair) for a, b in term.get_mappings(include_xrefs=True)},
        )

    def test_10_xrefs_with_provenance_object(self) -> None:
        """Test getting mappings."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            xref: cas:389-08-2 [{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        x = Reference(prefix="cas", identifier="cas:389-08-2")
        axioms = term._get_annotations(has_dbxref, x)
        self.assertEqual(1, len(axioms))
        axiom = axioms[0]
        self.assertIsInstance(axiom, Annotation)
        self.assertIsInstance(axiom.predicate, Reference)
        self.assertIsInstance(axiom.value, Reference)
        self.assertEqual(has_dbxref.pair, axiom.predicate.pair)
        self.assertEqual(CHARLIE.pair, axiom.value.pair)

    def test_10_xrefs_with_provenance_object_comment(self) -> None:
        """Test an xref, same as before but with a comment text."""
        ontology = from_str(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            xref: cas:389-08-2 [{CHARLIE.curie} "Comment-Text"]
        """)
        term = self.get_only_term(ontology)
        x = Reference(prefix="cas", identifier="cas:389-08-2")
        axioms = term._get_annotations(has_dbxref, x)
        self.assertEqual(1, len(axioms))
        axiom = axioms[0]
        self.assertIsInstance(axiom, Annotation)
        self.assertIsInstance(axiom.predicate, Reference)
        self.assertIsInstance(axiom.value, Reference)
        self.assertEqual(has_dbxref.pair, axiom.predicate.pair)
        self.assertEqual(CHARLIE.pair, axiom.value.pair)

    def test_10_xrefs_with_provenance_uri(self) -> None:
        """Test getting mappings."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            xref: cas:389-08-2 [https://example.org/test]
        """)
        term = self.get_only_term(ontology)
        x = Reference(prefix="cas", identifier="cas:389-08-2")
        axioms = term._get_annotations(has_dbxref, x)
        self.assertEqual(1, len(axioms))
        axiom = axioms[0]
        self.assertIsInstance(axiom, Annotation)
        self.assertIsInstance(axiom.predicate, Reference)
        self.assertIsInstance(axiom.value, OBOLiteral)
        self.assertEqual(has_dbxref.pair, axiom.predicate.pair)
        self.assertEqual(OBOLiteral.uri("https://example.org/test"), axiom.value)

    def test_11_builtin(self) -> None:
        """Test the ``builtin`` tag."""
        self.assert_boolean_flag("builtin")

    def test_12_property_malformed(self) -> None:
        """Test parsing a malformed property."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: nope
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.get_property_annotations())))

    def test_12_property_literal_bare(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: level "high"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("high", term.get_property(default_reference("chebi", "level")))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual(
            {
                "chebi_id": "1234",
                "property": "level",
                "value": "high",
                "datatype": "xsd:string",
                "language": "",
            },
            row,
        )

    def test_12_property_literal_typed(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: xyz "121.323" xsd:decimal

            [Typedef]
            id: xyz
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        ref = default_reference("chebi", "xyz")
        self.assertIn(ref, term.properties)
        self.assertEqual("121.323", term.get_property(ref))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("xyz", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])
        self.assertEqual("", row["language"])

    def test_12_property_bad_datatype(self) -> None:
        """Test parsing a property with an unparsable datatype."""
        text = """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: mass "121.323" NOPE:NOPE
        """
        with self.assertRaises(UnregisteredPrefixError):
            from_str(text, strict=True)
        ontology = from_str(text, strict=False)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.properties))

    def test_12_property_literal_url_questionable(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/chebi/mass "121.323" xsd:decimal
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("121.323", term.get_property(default_reference("chebi", "mass")))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("mass", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])
        self.assertEqual("", row["language"])

    def test_12_property_literal_url_default(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/chebi#mass "121.323" xsd:decimal
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("121.323", term.get_property(default_reference("chebi", "mass")))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("mass", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])
        self.assertEqual("", row["language"])

    def test_12_property_literal_datetime_unquoted(self) -> None:
        """Test parsing a property with a datetime object, with no quotes."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: oboInOwl:creation_date 2022-07-26T19:27:20Z xsd:dateTime
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("2022-07-26T19:27:20+00:00", term.get_property(v.obo_creation_date))

    def test_12_property_literal_datetime_quoted(self) -> None:
        """Test parsing a property with a datetime object, with quotes."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: oboInOwl:creation_date "2022-07-26T19:27:20Z" xsd:dateTime
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("2022-07-26T19:27:20+00:00", term.get_property(v.obo_creation_date))

    def test_12_property_literal_obo_purl(self) -> None:
        """Test using a full OBO PURL as the property."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/RO_0018033 CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertIn(Reference(prefix="RO", identifier="0018033"), term.properties)
        self.assertEqual("CHEBI:5678", term.get_property(is_conjugate_base_of))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual(
            {
                "chebi_id": "1234",
                "property": "RO:0018033",
                "value": "CHEBI:5678",
                "datatype": "",
                "language": "",
            },
            row,
        )

    def test_12_property_object_url(self) -> None:
        """Test parsing an object URI."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/RO_0018033 http://purl.obolibrary.org/obo/CHEBI_5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("CHEBI:5678", term.get_property(is_conjugate_base_of))

        df = ontology.get_properties_df()
        self.assertEqual(5, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual(
            {
                "chebi_id": "1234",
                "property": "RO:0018033",
                "value": "CHEBI:5678",
                "datatype": "",
                "language": "",
            },
            row,
        )

    def test_12_property_object_url_invalid(self) -> None:
        """Test parsing an object URI."""
        text = """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/RO_0018033 http://example.org/nope:nope
        """
        with self.assertRaises(UnparsableIRIError):
            from_str(text, strict=True)
        ontology = from_str(text, strict=False)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.properties))

    def test_12_property_literal_url(self) -> None:
        """Test using a full OBO PURL as the property."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: https://w3id.org/biolink/vocab/something CHEBI:5678
        """)
        td = TypeDef.from_triple(prefix="biolink", identifier="something")
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.properties))
        self.assertEqual("CHEBI:5678", term.get_property(td))

    def test_12_property_unparsable_object(self) -> None:
        """Test when an object can't be parsed."""
        text = """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: https://w3id.org/biolink/vocab/something NOPE:NOPE
            """

        with self.assertRaises(UnregisteredPrefixError):
            from_str(text, strict=True)

        ontology = from_str(text, strict=False)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.properties))

    def test_12_property_literal_url_unregistered(self) -> None:
        """Test using a full OBO PURL as the property."""
        with self.assertRaises(UnparsableIRIError):
            from_str(
                """\
                ontology: chebi

                [Term]
                id: CHEBI:1234
                property_value: https://example.com/nope/nope CHEBI:5678
                """,
                strict=True,
            )

        ontology = from_str(
            """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: https://example.com/nope/nope CHEBI:5678
            """,
            strict=False,
        )

        term = self.get_only_term(ontology)
        self.assertEqual(0, len(term.properties))

    def test_12_property_literal_object(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: rdfs:seeAlso hgnc:1234
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.properties)))
        self.assertIn(see_also.reference, term.properties)
        self.assertEqual("hgnc:1234", term.get_property(see_also))

    def test_12_property_object_with_string_dtype(self) -> None:
        """Test parsing a property with a literal object that has a string dtype."""
        # the dtype really shouldn't be here, so we have to special case it
        ontology = from_str("""\
            ontology: ro

            [Term]
            id: RO:0002160
            property_value: IAO:0000119 PMID:17921072 xsd:string
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.properties)))
        xx = term.get_property_objects(definition_source)
        self.assertEqual(1, len(xx))
        self.assertEqual(Reference(prefix="pubmed", identifier="17921072"), xx[0])

    def test_13_parent(self) -> None:
        """Test parsing out a parent."""
        ontology = from_str("""\
            ontology: chebi
            date: 20:11:2024 18:44

            [Term]
            id: CHEBI:1234
            is_a: CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual([Reference(prefix="CHEBI", identifier="5678")], term.parents)

        ontology = from_str("""\
            ontology: chebi
            date: 20:11:2024 18:44

            [Term]
            id: CHEBI:1234
            is_a: http://purl.obolibrary.org/obo/CHEBI_5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual([Reference(prefix="CHEBI", identifier="5678")], term.parents)

    def test_14_intersection_of(self) -> None:
        """Test the ``intersection_of`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1
            intersection_of: CHEBI:2
            intersection_of: RO:1234567 CHEBI:3
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            [
                Reference(prefix="CHEBI", identifier="2"),
                (
                    Reference(prefix="RO", identifier="1234567"),
                    Reference(prefix="CHEBI", identifier="3"),
                ),
            ],
            term.intersection_of,
        )

    def test_15_union_of(self) -> None:
        """Test the ``union_of`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1
            union_of: CHEBI:2
            union_of: CHEBI:3
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            [
                Reference(prefix="CHEBI", identifier="2"),
                Reference(prefix="CHEBI", identifier="3"),
            ],
            term.union_of,
        )

    def test_16_equivalent_to(self) -> None:
        """Test the ``equivalent_to`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1
            equivalent_to: CHEBI:2
            equivalent_to: CHEBI:3
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            [
                Reference(prefix="CHEBI", identifier="2"),
                Reference(prefix="CHEBI", identifier="3"),
            ],
            term.equivalent_to,
        )

    def test_17_disjoint_from(self) -> None:
        """Test the ``disjoint_from`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1
            disjoint_from: CHEBI:2
            disjoint_from: CHEBI:3
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(
            [
                Reference(prefix="CHEBI", identifier="2"),
                Reference(prefix="CHEBI", identifier="3"),
            ],
            term.disjoint_from,
        )

    def test_18_relationship_qualified_undefined(self) -> None:
        """Test parsing a relationship that's loaded in the defaults."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            relationship: RO:0018033 CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_18_relationship_qualified_defined(self) -> None:
        """Test relationship parsing that's defined."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            relationship: RO:0018033 CHEBI:5678

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_18_relationship_unqualified(self) -> None:
        """Test relationship parsing that relies on default referencing."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: xyz CHEBI:5678

            [Typedef]
            id: xyz
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.get_relationship(is_conjugate_base_of))
        r = default_reference("chebi", "xyz")
        td = TypeDef(reference=r)
        reference = term.get_relationship(td)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

        rr = list(ontology.iterate_filtered_relations(td))
        self.assertEqual(1, len(rr))

        rr2 = list(ontology.iterate_filtered_relations(is_conjugate_base_of))
        self.assertEqual(0, len(rr2))

    def test_18_relationship_bad_target(self) -> None:
        """Test an ontology with a version but no date."""
        text = """\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            relationship: RO:0018033 missing

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
        """

        with self.assertRaises(NotCURIEError):
            from_str(text, strict=True)

        ontology = from_str(text, strict=False)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.iterate_relations())))

    def test_18_default_relation(self):
        """Test parsing a default relation."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:100147
            relationship: derives_from drugbank:DB00779
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.relationships))
        self.assertIn(derives_from.reference, term.relationships)

    @unittest.skip(reason=REASON_OBONET_IMPL)
    def test_18_sssom_axiom(self) -> None:
        """Test SSSOM axioms."""
        ontology = from_str("""\
            ontology: go

            [Term]
            id: GO:0050069
            name: lysine dehydrogenase activity
            property_value: skos:exactMatch eccode:1.4.1.15 {dcterms:contributor=orcid:0000-0003-4423-4370}
        """)
        term = self.get_only_term(ontology)
        mappings = term.get_mappings(add_context=True)
        self.assertEqual(1, len(mappings))
        context = mappings[0][2]
        self.assertIsNotNone(context.contributor)
        self.assertEqual("0000-0003-4423-4370", context.contributor.identifier)

    # TODO created_by

    def test_20_creation_date(self) -> None:
        """Test parsing a property with a datetime object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            creation_date: 2022-07-26T19:27:20Z
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("2022-07-26T19:27:20+00:00", term.get_property(v.obo_creation_date))

    def test_20_creation_date_bad_format(self) -> None:
        """Test parsing a property with a datetime object."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            creation_date: asgasgag
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.get_property(v.obo_creation_date))

    def test_21_is_obsolete(self) -> None:
        """Test the ``is_obsolete`` tag."""
        self.assert_boolean_flag("is_obsolete")

    def test_22_replaced_by(self) -> None:
        """Test the ``replaced-by`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            replaced_by: CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        replaced = term.get_property_values(term_replaced_by)
        self.assertEqual(1, len(replaced))
        self.assertEqual(Reference(prefix="CHEBI", identifier="5678"), replaced[0])

    def test_23_consider(self) -> None:
        """Test the ``consider`` tag."""
        ontology = from_str("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            consider: CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        consider = term.get_property_values(see_also)
        self.assertEqual(1, len(consider))
        self.assertEqual(
            Reference(prefix="CHEBI", identifier="5678"),
            consider[0],
            msg=rf"""\Didn't get consider from the right place:

            properties: {dict(term.properties)}

            relationships: {dict(term.relationships)}
            """,
        )

    def test_get_references(self) -> None:
        """Test getting references from an ontology."""
        ontology = from_str("""\
            ontology: chebi
            date: 20:11:2024 18:44
            subsetdef: TESTSUBSET "test subset name"
            synonymtypedef: OMO:0000001 "E1 Name" EXACT

            [Typedef]
            id: RO:1234567

            [Term]
            id: CHEBI:1234
            is_a: CHEBI:5678
            subset: TESTSUBSET
        """)
        r1 = Reference(prefix="CHEBI", identifier="1234")
        r2 = Reference(prefix="CHEBI", identifier="5678")
        td1 = Reference(prefix="RO", identifier="1234567")
        ss1 = default_reference("chebi", "TESTSUBSET")
        std1 = Reference(prefix="OMO", identifier="0000001", name="E1 Name")
        expected_references = {
            r1.prefix: {r1, r2},
            td1.prefix: {td1},
            "obo": {ss1},
            std1.prefix: {std1},
            "dcterms": {v.has_description, v.has_license, v.has_title},
            v.has_dbxref.prefix: {v.has_exact_synonym},
        }
        self.assertEqual(expected_references, ontology._get_references())
