"""Tests for alternative identifiers."""

import unittest
from unittest import mock

from curies import Reference, ReferenceTuple

from pyobo import (
    get_id_name_mapping,
    get_name,
    get_name_by_curie,
    get_primary_curie,
    get_primary_identifier,
)
from pyobo.mocks import get_mock_id_alts_mapping, get_mock_id_name_mapping
from pyobo.struct.struct import Term, make_ad_hoc_ontology

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

    def test_get_name_alternate(self) -> None:
        """Test getting the hierarchy."""
        t1 = Term.from_triple(
            prefix="go", identifier="0001071", name="DNA-binding transcription factor activity"
        )
        ontology = make_ad_hoc_ontology(_ontology="go", terms=[t1])
        with mock.patch("pyobo.api.names.get_ontology", return_value=ontology):
            id_name = get_id_name_mapping("go", cache=False)
            self.assertEqual({t1.identifier: t1.name}, id_name)

            name = get_name(t1.prefix, t1.identifier, cache=False)
            self.assertIsNotNone(name)
            self.assertEqual(t1.name, name)
