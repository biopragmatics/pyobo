"""Tests for alternative identifiers."""

import importlib.util
import unittest
from contextlib import ExitStack
from unittest import mock

import bioregistry
from curies import Reference, ReferenceTuple
from curies import vocabulary as _v
from pydantic import ValidationError
from ssslm import LiteralMapping

import pyobo
from pyobo import Reference as PyOBOReference
from pyobo import (
    default_reference,
    get_name,
    get_name_by_curie,
    get_primary_curie,
    get_primary_identifier,
)
from pyobo.mocks import get_mock_id_alts_mapping, get_mock_id_name_mapping
from pyobo.ner import get_grounder
from pyobo.struct import vocabulary as v
from pyobo.struct.struct import Obo, Term, TypeDef, make_ad_hoc_ontology

mock_id_alts_mapping = get_mock_id_alts_mapping(
    {
        "go": {
            "0003700": ["0001071"],
        },
    }
)

mock_id_names_mapping = get_mock_id_name_mapping(
    {
        "go": {
            "0003700": "DNA-binding transcription factor activity",
        },
        "ncbitaxon": {
            "52818": "Allamanda cathartica",
        },
    }
)

TEST_P1 = "test"
TEST_P2 = "test2"

bioregistry.manager.synonyms[TEST_P1] = TEST_P1
bioregistry.manager.registry[TEST_P1] = bioregistry.Resource(
    prefix=TEST_P1,
    name="Test Semantic Space",
    pattern="^\\d+$",
)
bioregistry.manager.synonyms[TEST_P2] = TEST_P2
bioregistry.manager.registry[TEST_P2] = bioregistry.Resource(
    prefix=TEST_P2,
    name="Test Semantic Space 2",
)


def patch_ontologies(ontology: Obo, targets: list[str]) -> ExitStack:
    """Patch multiple ontologies."""
    stack = ExitStack()
    for target in targets:
        patch = mock.patch(target, return_value=ontology)
        stack.enter_context(patch)
    return stack


class TestAltIds(unittest.TestCase):
    """Tests for alternative identifiers."""

    def test_get_primary_errors(self):
        """Test when calling get_primary_identifier incorrectly."""
        with self.assertRaises(ValueError):
            get_primary_identifier("go")

        # if you try passing a string, you're on your own for error handling
        with self.assertRaises(ValidationError):
            self.assertIsNone(get_primary_curie("nope:nope", strict=False))
        with self.assertRaises(ValueError):
            get_primary_curie("nope:nope", strict=True)

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_get_primary(self, _, __):
        """Test upgrading an obsolete identifier."""
        primary_id = get_primary_identifier("go", "0001071")
        self.assertIsNotNone(primary_id)
        self.assertEqual("0003700", primary_id)
        name = get_name(ReferenceTuple("go", "0001071"))
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_get_primary_by_curie(self, _, __):
        """Test upgrading an obsolete CURIE."""
        primary_curie = get_primary_curie("go:0001071")
        self.assertIsNotNone(primary_curie)
        self.assertEqual("go:0003700", primary_curie)
        name = get_name_by_curie("go:0001071")
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_already_primary(self, _, __):
        """Test when you give a primary id."""
        primary_id = get_primary_identifier(ReferenceTuple("go", "0003700"))
        self.assertIsNotNone(primary_id)
        self.assertEqual("0003700", primary_id)
        name = get_name(ReferenceTuple("go", "0003700"))
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

        name = get_name(ReferenceTuple("go", "0003700"))
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

        name = get_name(Reference(prefix="go", identifier="0003700"))
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_get_primary_on_reference(self, _, __):
        """Test when you give a primary id."""
        self.assertEqual(
            "0003700", get_primary_identifier(Reference(prefix="go", identifier="0001071"))
        )

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_already_primary_by_curie(self, _, __):
        """Test when you give a primary CURIE."""
        primary_curie = get_primary_curie("go:0003700")
        self.assertIsNotNone(primary_curie)
        self.assertEqual("go:0003700", primary_curie)
        name = get_name_by_curie("go:0003700")
        self.assertIsNotNone(name)
        self.assertEqual("DNA-binding transcription factor activity", name)

    @mock_id_alts_mapping
    @mock_id_names_mapping
    def test_no_alts(self, _, __):
        """Test alternate behavior for nomenclature source with no alts."""
        primary_id = get_primary_identifier(ReferenceTuple("ncbitaxon", "52818"))
        self.assertEqual("52818", primary_id)
        self.assertEqual("Allamanda cathartica", get_name(ReferenceTuple("ncbitaxon", "52818")))

    def test_api(self) -> None:
        """Test getting the hierarchy.

        Run this with ``tox -e py -- tests/test_api.py``.
        """
        tr1 = default_reference(TEST_P1, "r1")
        td1 = TypeDef(reference=tr1)
        r1 = PyOBOReference(prefix=TEST_P1, identifier="1", name="test name")
        r2 = PyOBOReference(prefix=TEST_P1, identifier="2")
        r3 = PyOBOReference(prefix=TEST_P1, identifier="3")
        r2_1 = PyOBOReference(prefix=TEST_P2, identifier="X")
        r2_2 = PyOBOReference(prefix=TEST_P2, identifier="Y")
        syn1 = "ttt1"
        t1 = Term(reference=r1).append_alt(r2).append_synonym(syn1).append_xref(r2_1)
        t1.append_comment("test comment")
        t2 = Term(reference=r2)
        t3 = Term(reference=r3).append_parent(r1).append_exact_match(r2_2)
        terms = [t1, t2, t3]
        ontology = make_ad_hoc_ontology(TEST_P1, terms=terms, _typedefs=[td1])

        targets = [
            "pyobo.api.names.get_ontology",
            "pyobo.api.alts.get_ontology",
            "pyobo.api.properties.get_ontology",
            "pyobo.api.relations.get_ontology",
            "pyobo.api.edges.get_ontology",
            "pyobo.api.xrefs.get_ontology",
        ]
        with patch_ontologies(ontology, targets):
            # Alts

            ids_alts = pyobo.get_id_to_alts(TEST_P1, cache=False)
            self.assertEqual({"1": ["2"]}, ids_alts)

            alts_ids = pyobo.get_alts_to_id(TEST_P1, cache=False)
            self.assertEqual({"2": "1"}, alts_ids)

            self.assertEqual("1", pyobo.get_primary_identifier(r1, cache=False))
            self.assertEqual("1", pyobo.get_primary_identifier(r2, cache=False))

            self.assertEqual("test:1", pyobo.get_primary_curie(r1.curie, cache=False))
            self.assertEqual("test:1", pyobo.get_primary_curie(r2.curie, cache=False))

            # Names

            ids = pyobo.get_ids(TEST_P1, cache=False)
            self.assertEqual({r1.identifier, r2.identifier, r3.identifier}, ids)

            references = pyobo.get_references(TEST_P1, cache=False)
            self.assertEqual({r1, r2, r3, tr1}, references)

            id_name = pyobo.get_id_name_mapping(TEST_P1, cache=False)
            self.assertEqual({t1.identifier: t1.name}, id_name)

            name_id = pyobo.get_name_id_mapping(TEST_P1, cache=False)
            self.assertEqual({t1.name: t1.identifier}, name_id)

            self.assertEqual(t1.name, pyobo.get_name(r1, cache=False))
            self.assertEqual(t1.name, pyobo.get_name(r2, cache=False))

            # Xrefs
            d = pyobo.get_filtered_xrefs(TEST_P1, TEST_P2, cache=False, use_tqdm=False)
            self.assertEqual({"1": "X", "3": "Y"}, d)

            # Synonyms

            literal_mappings = pyobo.get_literal_mappings(TEST_P1, cache=False)
            expected = [
                LiteralMapping(
                    text="ttt1",
                    reference=r1,
                    predicate=PyOBOReference.from_reference(_v.has_related_synonym),
                    source=TEST_P1,
                ),
                LiteralMapping(
                    text="test name",
                    reference=r1,
                    predicate=PyOBOReference.from_reference(_v.has_label),
                    source=TEST_P1,
                ),
            ]
            self.assertEqual(expected, literal_mappings)

            if importlib.util.find_spec("gilda"):
                grounder = get_grounder(TEST_P1, cache=False)
                match = grounder.get_best_match(syn1)
                self.assertIsNotNone(match)
                self.assertEqual(TEST_P1, match.prefix)
                self.assertEqual("1", match.identifier)

            # Properties

            value = pyobo.get_property(
                r1.prefix, r1.identifier, prop=v.comment, cache=False, use_tqdm=False
            )
            self.assertEqual("test comment", value)

            edges = pyobo.get_edges(TEST_P1, cache=False, use_tqdm=False)
            self.assertEqual(
                {
                    (r3, v.is_a, r1),
                    (r1, v.alternative_term, r2),
                    (r1, v.has_dbxref, r2_1),
                    (r3, v.exact_match, r2_2),
                },
                set(edges),
            )

            graph = pyobo.get_hierarchy(TEST_P1, cache=False, use_tqdm=False)
            self.assertEqual(4, graph.number_of_nodes())
            self.assertIn(r1, graph)
            self.assertIn(r2, graph)
            self.assertIn(r3, graph)
            self.assertIn(tr1, graph)
            self.assertEqual(1, graph.number_of_edges())

            self.assertEqual(set(), pyobo.get_ancestors(r1, cache=False, use_tqdm=False))
            self.assertEqual(set(), pyobo.get_descendants(r3, cache=False, use_tqdm=False))
            self.assertEqual(set(), pyobo.get_children(r3, cache=False, use_tqdm=False))

            self.assertEqual({r1}, pyobo.get_ancestors(r3, cache=False, use_tqdm=False))
            self.assertEqual({r3}, pyobo.get_descendants(r1, cache=False, use_tqdm=False))
            self.assertEqual({r3}, pyobo.get_children(r1, cache=False, use_tqdm=False))

            self.assertTrue(pyobo.has_ancestor(r3, r1, cache=False, use_tqdm=False))
            self.assertTrue(pyobo.has_ancestor(*r3.pair, *r1.pair, cache=False, use_tqdm=False))
            self.assertFalse(pyobo.has_ancestor(r1, r3, cache=False, use_tqdm=False))
            self.assertFalse(pyobo.has_ancestor(*r1.pair, *r3.pair, cache=False, use_tqdm=False))
            self.assertTrue(pyobo.is_descendent(*r3.pair, *r1.pair, cache=False, use_tqdm=False))
            self.assertTrue(pyobo.is_descendent(r3, r1, cache=False, use_tqdm=False))
            self.assertFalse(pyobo.is_descendent(r1, r3, cache=False, use_tqdm=False))
            self.assertFalse(pyobo.is_descendent(*r1.pair, *r3.pair, cache=False, use_tqdm=False))
