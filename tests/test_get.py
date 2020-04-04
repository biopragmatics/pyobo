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
    """"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = obonet.read_obo(TEST_CHEBI_OBO_PATH)

    def test_get_graph_typedefs(self):
        """Test getting type definitions from an :mod:`obonet` graph."""
        pairs = {
            (typedef.prefix, typedef.identifier)
            for typedef in iterate_graph_typedefs(self.graph)
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
        xrefs = list(iterate_node_xrefs(data))
        self.assertEqual(7, len(xrefs))
        # NOTE the prefixes are remapped by PyOBO
        self.assertEqual({'pubmed', 'cas', 'beilstein', 'reaxys'}, {
            xref.prefix
            for xref in xrefs
        })
        self.assertEqual(
            {
                ('reaxys', '3570522'), ('beilstein', '3570522'), ('cas', '429-41-4'),
                ('pubmed', '21142041'), ('pubmed', '21517057'), ('pubmed', '22229781'), ('pubmed', '15074950'),
            },
            {(xref.prefix, xref.identifier) for xref in xrefs}
        )

    def test_get_node_relations(self):
        """Test getting relations from a node in a :mod:`obonet` graph."""
        data = self.graph.nodes['CHEBI:17051']
        relations = list(iterate_node_relationships(data, 'chebi'))
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

    def test_get_obo(self):
        """Test getting an OBO document."""
        obo = get('chebi', url=TEST_CHEBI_OBO_PATH, local=True)
        terms = list(obo.iter_terms())
        self.assertEqual(18, len(terms))
