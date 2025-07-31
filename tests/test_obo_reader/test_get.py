"""Tests for getting OBO."""

import unittest
from operator import attrgetter

import obonet
from curies import ReferenceTuple

from pyobo import Reference, Synonym, SynonymTypeDef, default_reference, get_ontology
from pyobo.struct.obo.reader import (
    _extract_definition,
    _extract_synonym,
    iterate_graph_synonym_typedefs,
    iterate_node_properties,
    iterate_node_relationships,
    iterate_node_synonyms,
    iterate_node_xrefs,
    iterate_typedefs,
)
from pyobo.struct.struct import acronym
from tests.constants import TEST_CHEBI_OBO_PATH, chebi_patch


class TestParseObonet(unittest.TestCase):
    """Test parsing OBO."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test case with a mock ChEBI OBO."""
        cls.ontology = "chebi"
        cls.graph = obonet.read_obo(TEST_CHEBI_OBO_PATH)

    def test_get_graph_typedefs(self):
        """Test getting type definitions from an :mod:`obonet` graph."""
        pairs = {
            typedef.pair
            for typedef in iterate_typedefs(self.graph, ontology_prefix="chebi", upgrade=False)
        }
        self.assertIn(ReferenceTuple("obo", "chebi#has_major_microspecies_at_pH_7_3"), pairs)

    def test_get_graph_synonym_typedefs(self):
        """Test getting synonym type definitions from an :mod:`obonet` graph."""
        synonym_typedefs = sorted(
            iterate_graph_synonym_typedefs(
                self.graph, ontology_prefix=self.ontology, upgrade=False
            ),
            key=attrgetter("curie"),
        )
        self.assertEqual(
            sorted(
                [
                    SynonymTypeDef(
                        reference=default_reference(
                            prefix="chebi", identifier="IUPAC_NAME", name="IUPAC NAME"
                        )
                    ),
                    SynonymTypeDef(
                        reference=default_reference(
                            prefix="chebi", identifier="BRAND_NAME", name="BRAND NAME"
                        )
                    ),
                    SynonymTypeDef(
                        reference=default_reference(prefix="chebi", identifier="INN", name="INN")
                    ),
                ],
                key=attrgetter("curie"),
            ),
            synonym_typedefs,
        )

    def test_extract_definition(self):
        """Test extracting a definition."""
        expected_text = "Test Text."

        for s, expected_references in [
            (f'"{expected_text}"', []),
            (f'"{expected_text}" []', []),
            (f'"{expected_text}" [PMID:1234]', [Reference(prefix="pubmed", identifier="1234")]),
            (
                f'"{expected_text}" [PMID:1234, PMID:1235]',
                [
                    Reference(prefix="pubmed", identifier="1234"),
                    Reference(prefix="pubmed", identifier="1235"),
                ],
            ),
        ]:
            with self.subTest(s=s):
                actual_text, actual_references = _extract_definition(
                    s, node=Reference(prefix="chebi", identifier="1234"), ontology_prefix="chebi"
                )
                self.assertEqual(expected_text, actual_text)
                self.assertEqual(expected_references, actual_references)

    def test_extract_definition_with_escapes(self):
        """Test extracting a definition with escapes in it."""
        expected_text = """The canonical 3' splice site has the sequence "AG"."""
        s = """"The canonical 3' splice site has the sequence \\"AG\\"." [PMID:1234]"""
        actual_text, actual_references = _extract_definition(
            s,
            strict=True,
            node=Reference(prefix="chebi", identifier="1234"),
            ontology_prefix="chebi",
        )
        self.assertEqual(expected_text, actual_text)
        self.assertEqual([Reference(prefix="pubmed", identifier="1234")], actual_references)

    def test_extract_synonym(self):
        """Test extracting synonym strings."""
        iupac_name = SynonymTypeDef(
            reference=default_reference(prefix="chebi", identifier="IUPAC_NAME", name="IUPAC NAME")
        )
        synoynym_typedefs = {
            iupac_name.pair: iupac_name,
            acronym.pair: acronym,
        }

        for expected_synonym, text in [
            (
                Synonym(
                    name="LTEC I",
                    specificity="EXACT",
                    type=iupac_name.reference,
                    provenance=[Reference(prefix="orphanet", identifier="93938")],
                ),
                '"LTEC I" EXACT IUPAC_NAME [Orphanet:93938]',
            ),
            (
                Synonym(
                    name="LTEC I",
                    specificity="EXACT",
                    provenance=[Reference(prefix="orphanet", identifier="93938")],
                ),
                '"LTEC I" EXACT [Orphanet:93938]',
            ),
            (
                Synonym(
                    name="LTEC I",
                    specificity=None,
                    provenance=[Reference(prefix="orphanet", identifier="93938")],
                ),
                '"LTEC I" [Orphanet:93938]',
            ),
            (
                Synonym(name="LTEC I", specificity=None),
                '"LTEC I" []',
            ),
            (
                Synonym(name="HAdV-A", specificity="BROAD", type=acronym.reference),
                '"HAdV-A" BROAD OMO:0003012 []',
            ),
            (
                Synonym(name="HAdV-A", specificity="BROAD", type=acronym.reference),
                '"HAdV-A" BROAD omo:0003012 []',
            ),
            (
                Synonym(name="HAdV-A", specificity=None, type=acronym.reference),
                '"HAdV-A" OMO:0003012 []',
            ),
            (
                Synonym(name="HAdV-A", specificity=None, type=acronym.reference),
                '"HAdV-A" omo:0003012 []',
            ),
        ]:
            with self.subTest(s=text):
                actual_synonym = _extract_synonym(
                    text,
                    synoynym_typedefs,
                    node=Reference(prefix="chebi", identifier="1234"),
                    ontology_prefix="chebi",
                    upgrade=False,
                )
                self.assertIsInstance(actual_synonym, Synonym)
                self.assertEqual(expected_synonym, actual_synonym)

    def test_get_node_synonyms(self):
        """Test getting synonyms from a node in a :mod:`obonet` graph."""
        iupac_name = SynonymTypeDef(
            reference=default_reference(prefix="chebi", identifier="IUPAC_NAME", name="IUPAC NAME")
        )
        synoynym_typedefs = {
            iupac_name.pair: iupac_name,
        }
        data = self.graph.nodes["CHEBI:51990"]
        synonyms = list(
            iterate_node_synonyms(
                data,
                synoynym_typedefs,
                node=Reference(prefix="chebi", identifier="51990"),
                ontology_prefix="chebi",
                upgrade=False,
            )
        )
        self.assertEqual(1, len(synonyms))
        synonym = synonyms[0]
        self.assertEqual(
            "N,N,N-tributylbutan-1-aminium fluoride", synonym.name, msg="name parsing failed"
        )
        self.assertEqual("EXACT", synonym.specificity, msg="specificity parsing failed")
        self.assertEqual(iupac_name.reference, synonym.type)

    def test_get_node_properties(self):
        """Test getting properties from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes["CHEBI:51990"]
        properties = list(
            iterate_node_properties(
                data,
                node=Reference(prefix="chebi", identifier="51990"),
                ontology_prefix="chebi",
                upgrade=False,
                context="",
            )
        )
        t_prop = default_reference("chebi", "monoisotopicmass")
        self.assertIn(t_prop, {prop for prop, value in properties})
        self.assertEqual(1, sum(prop == t_prop for prop, value in properties))
        value = next(value.value for prop, value in properties if prop == t_prop)
        self.assertIsInstance(value, str)
        self.assertEqual("261.28318", value)

    def test_get_node_xrefs(self):
        """Test getting parents from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes["CHEBI:51990"]
        xrefs = [
            xref
            for xref, _ in iterate_node_xrefs(
                data=data,
                ontology_prefix="chebi",
                node=Reference(prefix="chebi", identifier="51990"),
                upgrade=True,
            )
        ]
        self.assertEqual(7, len(xrefs))
        # NOTE the prefixes are remapped by Bioregistry
        self.assertEqual({"pubmed", "cas", "reaxys"}, {xref.prefix for xref in xrefs})
        self.assertEqual(
            {
                ("reaxys", "3570522"),
                ("cas", "429-41-4"),
                ("pubmed", "21142041"),
                ("pubmed", "21517057"),
                ("pubmed", "22229781"),
                ("pubmed", "15074950"),
            },
            {(xref.prefix, xref.identifier) for xref in xrefs},
        )

    def test_get_node_relations(self):
        """Test getting relations from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes["CHEBI:17051"]
        relations = list(
            iterate_node_relationships(
                data,
                node=Reference(prefix="chebi", identifier="17051"),
                ontology_prefix="chebi",
                upgrade=False,
            )
        )
        self.assertEqual(1, len(relations))
        typedef, target = relations[0]

        self.assertIsNotNone(target)
        self.assertIsInstance(target, Reference)
        self.assertEqual(("chebi", "29228"), target.pair)

        self.assertIsNotNone(typedef)
        self.assertIsInstance(typedef, Reference)
        self.assertEqual(("obo", "chebi#is_conjugate_base_of"), typedef.pair)


class TestGet(unittest.TestCase):
    """Test generation of OBO objects."""

    def setUp(self) -> None:
        """Set up the test with the mock ChEBI OBO file."""
        with chebi_patch:
            self.ontology = get_ontology("chebi", cache=False)

    def test_get_id_alts_mapping(self):
        """Make sure the alternative ids are mapped properly.

        .. code-block::

            [Term]
            id: CHEBI:16042
            name: halide anion
            alt_id: CHEBI:5605
            alt_id: CHEBI:14384
        """
        id_alts_mapping = self.ontology.get_id_alts_mapping()
        self.assertNotIn("C00462", id_alts_mapping)
        self.assertIn("16042", id_alts_mapping, msg="halide anion alt_id fields not parsed")
        self.assertEqual({"5605", "14384"}, set(id_alts_mapping["16042"]))

    def test_typedefs(self):
        """Test typedefs."""
        xx = default_reference("chebi", "has_major_microspecies_at_pH_7_3")
        td = self.ontology._index_typedefs()
        self.assertIn(xx.pair, td)
        self.assertIn(ReferenceTuple("ro", "0018033"), td)
