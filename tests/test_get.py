# -*- coding: utf-8 -*-

"""Tests for getting OBO."""

import unittest
from operator import attrgetter

import obonet

from pyobo import SynonymTypeDef, get
from pyobo.struct import Reference
from pyobo.struct.struct import (
    iterate_graph_synonym_typedefs, iterate_graph_typedefs, iterate_node_parents, iterate_node_properties,
    iterate_node_relationships, iterate_node_synonyms, iterate_node_xrefs,
)
from tests.constants import TEST_CHEBI_OBO_PATH


class TestParseObonet(unittest.TestCase):
    """Test parsing OBO."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test case with a mock ChEBI OBO."""
        cls.graph = obonet.read_obo(TEST_CHEBI_OBO_PATH)

    def test_get_graph_typedefs(self):
        """Test getting type definitions from an :mod:`obonet` graph."""
        pairs = {
            (typedef.prefix, typedef.identifier)
            for typedef in iterate_graph_typedefs(self.graph, 'chebi')
        }
        self.assertIn(('chebi', 'has_part'), pairs)

    def test_get_graph_synonym_typedefs(self):
        """Test getting synonym type definitions from an :mod:`obonet` graph."""
        synonym_typedefs = sorted(iterate_graph_synonym_typedefs(self.graph), key=attrgetter('id'))
        self.assertEqual(
            sorted([
                SynonymTypeDef(id='IUPAC_NAME', name='IUPAC NAME'),
                SynonymTypeDef(id='BRAND_NAME', name='BRAND NAME'),
                SynonymTypeDef(id='INN', name='INN'),
            ], key=attrgetter('id')),
            synonym_typedefs,
        )

    def test_get_node_synonyms(self):
        """Test getting synonyms from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:51990']
        synonyms = list(iterate_node_synonyms(data))
        self.assertEqual(1, len(synonyms))
        synonym = synonyms[0]
        self.assertEqual('N,N,N-tributylbutan-1-aminium fluoride', synonym.name, msg='name parsing failed')
        self.assertEqual('EXACT', synonym.specificity, msg='specificity parsing failed')
        # TODO implement
        # self.assertEqual(SynonymTypeDef(id='IUPAC_NAME', name='IUPAC NAME'), synonym.type)

    def test_get_node_properties(self):
        """Test getting properties from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:51990']
        properties = list(iterate_node_properties(data))
        t_prop = 'http://purl.obolibrary.org/obo/chebi/monoisotopicmass'
        self.assertIn(t_prop, {prop for prop, value in properties})
        self.assertEqual(1, sum(prop == t_prop for prop, value in properties))
        value = [value for prop, value in properties if prop == t_prop][0]
        self.assertEqual('261.28318', value)

    def test_get_node_parents(self):
        """Test getting parents from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:51990']
        parents = list(iterate_node_parents(data))
        self.assertEqual(2, len(parents))
        self.assertEqual({'24060', '51992'}, {
            parent.identifier
            for parent in parents
        })
        self.assertEqual({'chebi'}, {
            parent.prefix
            for parent in parents
        })

    def test_get_node_xrefs(self):
        """Test getting parents from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:51990']
        xrefs = list(iterate_node_xrefs(prefix='chebi', data=data))
        self.assertEqual(7, len(xrefs))
        # NOTE the prefixes are remapped by Bioregistry
        self.assertEqual({'pubmed', 'cas', 'reaxys'}, {
            xref.prefix
            for xref in xrefs
        })
        self.assertEqual(
            {
                ('reaxys', '3570522'), ('cas', '429-41-4'),
                ('pubmed', '21142041'), ('pubmed', '21517057'), ('pubmed', '22229781'), ('pubmed', '15074950'),
            },
            {(xref.prefix, xref.identifier) for xref in xrefs},
        )

    def test_get_node_relations(self):
        """Test getting relations from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:17051']
        relations = list(iterate_node_relationships(data, default_prefix='chebi'))
        self.assertEqual(1, len(relations))
        typedef, target = relations[0]

        self.assertIsNotNone(target)
        self.assertIsInstance(target, Reference)
        self.assertEqual('chebi', target.prefix)
        self.assertEqual('29228', target.identifier)

        self.assertIsNotNone(typedef)
        self.assertIsInstance(typedef, Reference)
        self.assertEqual('chebi', typedef.prefix)
        self.assertEqual('is_conjugate_base_of', typedef.identifier)


class TestGet(unittest.TestCase):
    """Test generation of OBO objects."""

    def setUp(self) -> None:
        """Set up the test with the mock ChEBI OBO file."""
        # TODO use mock
        self.obo = get('chebi', url=TEST_CHEBI_OBO_PATH, local=True)

    def test_get_terms(self):
        """Test getting an OBO document."""
        terms = list(self.obo)
        self.assertEqual(18, len(terms))

    def test_get_id_alts_mapping(self):
        """Make sure the alternative ids are mapped properly.

        .. code-block::

            [Term]
            id: CHEBI:16042
            name: halide anion
            alt_id: CHEBI:5605
            alt_id: CHEBI:14384
        """
        id_alts_mapping = self.obo.get_id_alts_mapping()
        self.assertIn('16042', id_alts_mapping)
        self.assertEqual({'5605', '14384'}, set(id_alts_mapping['16042']))
