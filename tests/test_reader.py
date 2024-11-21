"""Tests for the reader."""

import datetime
import unittest
from io import StringIO
from textwrap import dedent

from obonet import read_obo

from pyobo import Obo, Reference, Term
from pyobo.reader import from_obonet, get_first_nonescaped_quote
from pyobo.struct import default_reference
from pyobo.struct.struct import DEFAULT_SYNONYM_TYPE
from pyobo.struct.typedef import TypeDef, is_conjugate_base_of, see_also

CHARLIE = Reference(prefix="orcid", identifier="0000-0003-4423-4370")


def _read(text: str, *, strict: bool = True) -> Obo:
    text = dedent(text).strip()
    io = StringIO()
    io.write(text)
    io.seek(0)
    graph = read_obo(io)
    return from_obonet(graph, strict=strict)


class TestUtils(unittest.TestCase):
    """Test utilities for the reader."""

    def test_first_nonescaped_quote(self):
        """Test finding the first non-escaped double quote."""
        self.assertEqual(0, get_first_nonescaped_quote('"'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc'))
        self.assertEqual(0, get_first_nonescaped_quote('"abc"'))
        self.assertEqual(2, get_first_nonescaped_quote('\\""'))
        self.assertEqual(3, get_first_nonescaped_quote('abc"'))
        self.assertEqual(3, get_first_nonescaped_quote('abc""'))
        self.assertIsNone(get_first_nonescaped_quote("abc"))
        self.assertIsNone(get_first_nonescaped_quote('abc\\"'))
        self.assertIsNone(get_first_nonescaped_quote('\\"hello\\"'))


class TestReader(unittest.TestCase):
    """Test the reader."""

    def test_unknown_ontology_prefix(self) -> None:
        """Test an ontology with an unknown prefix."""
        with self.assertRaises(ValueError) as exc:
            _read("""\
                ontology: nope

                [Term]
                id: CHEBI:1234
            """)
        self.assertEqual("unknown prefix: nope", exc.exception.args[0])

    def test_missing_date_version(self) -> None:
        """Test an ontology with a missing date and version."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    def test_bad_date_format(self) -> None:
        """Test an ontology with a malformed date and no version."""
        ontology = _read("""\
            ontology: chebi
            date: aabbccddeee

            [Term]
            id: CHEBI:1234
        """)
        self.assertIsNone(ontology.date)
        self.assertIsNone(ontology.data_version)

    def test_date_no_version(self) -> None:
        """Test an ontology with a date but no version."""
        ontology = _read("""\
            ontology: chebi
            date: 20:11:2024 18:44

            [Term]
            id: CHEBI:1234
        """)
        self.assertEqual(datetime.datetime(2024, 11, 20, 18, 44), ontology.date)
        self.assertEqual("2024-11-20", ontology.data_version)

    def get_only_term(self, ontology: Obo) -> Term:
        """Assert there is only a single term in the ontology and return it."""
        terms = list(ontology.iter_terms())
        self.assertEqual(1, len(terms))
        term = terms[0]
        return term

    def test_minimal(self) -> None:
        """Test an ontology with a version but no date."""
        ontology = _read("""\
            data-version: 185
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            def: "Test definition" [orcid:1234-1234-1234]
            xref: drugbank:DB1234567
        """)
        self.assertEqual([], ontology.typedefs)
        self.assertEqual([], ontology.synonym_typedefs)

        term = self.get_only_term(ontology)
        self.assertEqual("Test definition", term.definition)
        self.assertEqual(1, len(term.xrefs))
        xref = term.xrefs[0]
        self.assertEqual("drugbank:DB1234567", xref.curie)

    def test_relationship_qualified_undefined(self) -> None:
        """Test parsing a relationship that's loaded in the defaults."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: RO:0018033 CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_relationship_qualified_defined(self) -> None:
        """Test relationship parsing that's defined."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: RO:0018033 CHEBI:5678

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
        """)
        term = self.get_only_term(ontology)
        reference = term.get_relationship(is_conjugate_base_of)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_relationship_unqualified(self) -> None:
        """Test relationship parsing that relies on default referencing."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: is_conjugate_base_of CHEBI:5678

            [Typedef]
            id: is_conjugate_base_of
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.get_relationship(is_conjugate_base_of))
        r = default_reference("chebi", "is_conjugate_base_of")
        td = TypeDef(reference=r)
        reference = term.get_relationship(td)
        self.assertIsNotNone(reference)
        self.assertEqual("chebi:5678", reference.curie)

    def test_relationship_missing(self) -> None:
        """Test parsing a relationship that isn't defined."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            name: Test Name
            relationship: nope CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.iterate_relations())))

    def test_relationship_bad_target(self) -> None:
        """Test an ontology with a version but no date."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            relationship: RO:0018033 missing

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.iterate_relations())))

    def test_property_malformed(self) -> None:
        """Test parsing a malformed property."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: nope
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.iterate_properties())))

    def test_property_literal_bare(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: level "high"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.annotations_literal)))
        self.assertEqual("high", term.get_property(default_reference("chebi", "level")))

        df = ontology.get_properties_df()
        self.assertEqual(4, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual(
            {"chebi_id": "1234", "property": "level", "value": "high", "datatype": "xsd:string"},
            row,
        )

    def test_property_literal_typed(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: mass "121.323" xsd:decimal
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.annotations_literal)))
        self.assertEqual("121.323", term.get_property(default_reference("chebi", "mass")))

        df = ontology.get_properties_df()
        self.assertEqual(4, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("mass", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])

    def test_property_literal_url_questionable(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/chebi/mass "121.323" xsd:decimal
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.annotations_literal)))
        self.assertEqual("121.323", term.get_property(default_reference("chebi", "mass")))

        df = ontology.get_properties_df()
        self.assertEqual(4, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("mass", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])

    def test_property_literal_url_default(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/chebi#mass "121.323" xsd:decimal
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(list(term.annotations_literal)))
        self.assertEqual("121.323", term.get_property(default_reference("chebi", "mass")))

        df = ontology.get_properties_df()
        self.assertEqual(4, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual("1234", row["chebi_id"])
        self.assertEqual("mass", row["property"])
        self.assertEqual("121.323", row["value"])
        self.assertEqual("xsd:decimal", row["datatype"])

    def test_property_literal_obo_purl(self) -> None:
        """Test using a full OBO PURL as the property."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: http://purl.obolibrary.org/obo/RO_0018033 CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.annotations_literal)))
        self.assertEqual(1, len(list(term.annotations_object)))
        self.assertEqual("CHEBI:5678", term.get_property(is_conjugate_base_of))

        df = ontology.get_properties_df()
        self.assertEqual(4, len(df.columns))
        self.assertEqual(1, len(df))
        row = dict(df.iloc[0])
        self.assertEqual(
            {"chebi_id": "1234", "property": "RO:0018033", "value": "CHEBI:5678", "datatype": ""},
            row,
        )

    def test_property_literal_url(self) -> None:
        """Test using a full OBO PURL as the property."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: https://w3id.org/biolink/vocab/something CHEBI:5678
        """)
        td = TypeDef.from_curie("biolink:something")
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.annotations_literal)))
        self.assertEqual(1, len(list(term.annotations_object)))
        self.assertEqual("CHEBI:5678", term.get_property(td))

    def test_property_literal_url_unregistered(self) -> None:
        """Test using a full OBO PURL as the property."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: https://example.com/nope/nope CHEBI:5678
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.annotations_literal)))
        self.assertEqual(0, len(list(term.annotations_object)))

    def test_property_literal_object(self) -> None:
        """Test parsing a property with a literal object."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            property_value: rdfs:seeAlso hgnc:1234
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(0, len(list(term.annotations_literal)))
        self.assertEqual(1, len(list(term.annotations_object)))
        self.assertEqual("hgnc:1234", term.get_property(see_also))

    def test_node_unparsable(self) -> None:
        """Test loading an ontology with unparsable nodes.."""
        ontology = _read(
            """\
            ontology: chebi

            [Term]
            id: nope:1234
        """,
            strict=False,
        )
        self.assertEqual(0, len(list(ontology.iter_terms())))

    def test_malformed_typedef(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        with self.assertRaises(KeyError) as exc:
            _read("""\
                ontology: chebi

                [Typedef]
                name: nope
            """)
        self.assertEqual("typedef is missing an `id`", exc.exception.args[0])

    def test_typedef_xref(self) -> None:
        """Test loading an ontology with unparsable nodes."""
        ontology = _read("""\
            ontology: chebi

            [Typedef]
            id: RO:0018033
            name: is conjugate base of
            xref: debio:0000010
        """)
        self.assertEqual(1, len(ontology.typedefs))
        self.assertEqual(is_conjugate_base_of.pair, ontology.typedefs[0].pair)

    def test_definition_missing_start_quote(self) -> None:
        """Test parsing a definition missing a starting quote."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: malformed definition without quotes
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.definition)

    def test_definition_missing_end_quote(self) -> None:
        """Test parsing a definition missing an ending quote."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "malformed definition without quotes
        """)
        term = self.get_only_term(ontology)
        self.assertIsNone(term.definition)

    def test_definition_no_provenance(self) -> None:
        """Test parsing a term with a definition and no provenance brackets."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)

    def test_definition_empty_provenance(self) -> None:
        """Test parsing a term with a definition and empty provenance."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234" []
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)

    def test_definition_with_provenance(self) -> None:
        """Test parsing a term with a definition and provenance."""
        ontology = _read(f"""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            def: "definition of CHEBI:1234" [{CHARLIE.curie}]
        """)
        term = self.get_only_term(ontology)
        self.assertEqual("definition of CHEBI:1234", term.definition)
        self.assertEqual(1, len(term.provenance))
        self.assertEqual(CHARLIE, term.provenance[0])

    def test_synonym_minimal(self) -> None:
        """Test parsing a synonym just the text."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I"
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        self.assertEqual("LTEC I", synonym.name)
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(DEFAULT_SYNONYM_TYPE, synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_synonym_with_specificity(self) -> None:
        """Test parsing a synonym with specificity."""
        ontology = _read("""\
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
        self.assertEqual(DEFAULT_SYNONYM_TYPE, synonym.type)
        self.assertEqual([], synonym.provenance)

    def test_synonym_with_type_missing_def(self) -> None:
        """Test parsing a synonym with type, but missing type def."""
        ontology = _read("""\
            ontology: chebi

            [Term]
            id: CHEBI:1234
            synonym: "LTEC I" OMO:1234567
        """)
        term = self.get_only_term(ontology)
        self.assertEqual(1, len(term.synonyms))
        synonym = term.synonyms[0]
        #  this is because no typedef existed
        self.assertEqual(DEFAULT_SYNONYM_TYPE, synonym.type)

    def test_synonym_with_type(self) -> None:
        """Test parsing a synonym with type."""
        ontology = _read("""\
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
        self.assertEqual("EXACT", synonym.specificity)
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type.reference)
        self.assertEqual([], synonym.provenance)

    def test_synonym_with_type_and_specificity(self) -> None:
        """Test parsing a synonym with specificity and type."""
        ontology = _read("""\
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
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type.reference)
        self.assertEqual([], synonym.provenance)

    def test_synonym_with_empty_prov(self) -> None:
        """Test parsing a synonym with specificity,type, and explicit empty provenance."""
        ontology = _read("""\
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
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type.reference)
        self.assertEqual([], synonym.provenance)

    def test_synonym_no_type(self) -> None:
        """Test parsing a synonym with specificity and provenance."""
        ontology = _read(f"""\
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
        self.assertEqual(DEFAULT_SYNONYM_TYPE, synonym.type)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )

    def test_synonym_full(self) -> None:
        """Test parsing a synonym with specificity, type, and provenance."""
        ontology = _read(f"""\
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
        self.assertEqual(Reference(prefix="omo", identifier="1234567"), synonym.type.reference)
        self.assertEqual(
            [
                Reference(prefix="orphanet", identifier="93938"),
                CHARLIE,
            ],
            synonym.provenance,
        )
