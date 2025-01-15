"""Tests for alternative identifiers."""

import unittest
from contextlib import ExitStack
from unittest import mock

import bioregistry
from curies import Reference, ReferenceTuple

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

bioregistry.manager.synonyms[TEST_P1] = TEST_P1
bioregistry.manager.registry[TEST_P1] = bioregistry.Resource(
    prefix=TEST_P1,
    name="Test Semantic Space",
    pattern="^\\d+$",
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
        name = get_name("go", "0001071")
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
        primary_id = get_primary_identifier("go", "0003700")
        self.assertIsNotNone(primary_id)
        self.assertEqual("0003700", primary_id)
        name = get_name("go", "0003700")
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
        primary_id = get_primary_identifier("ncbitaxon", "52818")
        self.assertEqual("52818", primary_id)
        self.assertEqual("Allamanda cathartica", get_name("ncbitaxon", "52818"))

    def test_api(self) -> None:
        """Test getting the hierarchy."""
        tr1 = default_reference(TEST_P1, "r1")
        td1 = TypeDef(reference=tr1)
        r1 = PyOBOReference(prefix=TEST_P1, identifier="1", name="test name")
        r2 = PyOBOReference(prefix=TEST_P1, identifier="2")
        r3 = PyOBOReference(prefix=TEST_P1, identifier="3")
        t1 = Term(reference=r1).append_alt(r2)
        t1.append_comment("test comment")
        t2 = Term(reference=r2)
        t3 = Term(reference=r3).append_parent(r1)
        terms = [t1, t2, t3]
        ontology = make_ad_hoc_ontology(TEST_P1, terms=terms, _typedefs=[td1])

        with patch_ontologies(
            ontology,
            [
                "pyobo.api.names.get_ontology",
                "pyobo.api.alts.get_ontology",
                "pyobo.api.properties.get_ontology",
            ],
        ):
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
            self.assertEqual({t.identifier for t in terms}, ids)

            id_name = pyobo.get_id_name_mapping(TEST_P1, cache=False)
            self.assertEqual({t1.identifier: t1.name}, id_name)

            name_id = pyobo.get_name_id_mapping(TEST_P1, cache=False)
            self.assertEqual({t1.name: t1.identifier}, name_id)

            self.assertEqual(t1.name, pyobo.get_name(r1, cache=False))
            self.assertEqual(t1.name, pyobo.get_name(r2, cache=False))

            # Properties

            value = pyobo.get_property(r1.prefix, r1.identifier, prop=v.comment, cache=False)
            self.assertEqual("test comment", value)

            edges = pyobo.get_edges(TEST_P1, cache=False)
            self.assertEqual({(r3, v.is_a, r1), (r1, v.alternative_term, r2)}, set(edges))
