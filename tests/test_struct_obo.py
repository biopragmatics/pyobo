"""Test for OBO header."""

import unittest
from collections.abc import Iterable
from textwrap import dedent

from pyobo import default_reference
from pyobo.struct.struct import Obo, make_ad_hoc_ontology


class TestOBOHeader(unittest.TestCase):
    """Test ontologies."""

    def assert_lines(self, text: str, lines: Iterable[str]) -> None:
        """Assert the lines are equal."""
        self.assertEqual(dedent(text).strip(), "\n".join(lines).strip())

    def assert_obo_lines(self, text, ontology: Obo) -> None:
        """Assert OBO header has the right lines."""
        self.assert_lines(text, ontology.iterate_obo_lines())

    def test_2_data_version(self) -> None:
        """Test ontology definition."""
        ontology = make_ad_hoc_ontology(
            ontology="xxx",
            _data_version="1.0",
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            data-version: 1.0
            ontology: xxx
            """,
            ontology,
        )

    def test_5_data_version(self) -> None:
        """Test ontology definition."""
        ontology = make_ad_hoc_ontology(
            ontology="xxx",
            _auto_generated_by="test",
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            auto-generated-by: test
            ontology: xxx
            """,
            ontology,
        )

    def test_6_import(self) -> None:
        """Test imports."""

    def test_7_subsets(self) -> None:
        """Test ontology definition."""
        ontology = make_ad_hoc_ontology(
            _ontology="xxx",
            _subsetdefs=[(default_reference("xxx", "HELLO"), "test")],
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            subsetdef: HELLO "test"
            ontology: xxx
            """,
            ontology,
        )

        ontology = make_ad_hoc_ontology(
            _ontology="xxx",
            _subsetdefs=[(default_reference("go", "HELLO"), "test")],
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            subsetdef: obo:go#HELLO "test"
            ontology: xxx
            """,
            ontology,
        )

    def test_8_synonymtypedef(self) -> None:
        """Test ontology synonym type definitions."""

    def test_9_default_namespace(self) -> None:
        """Test default namespace."""

    def test_10_namespace_id_rule(self) -> None:
        """Test namespace-id-rule."""

    def test_11_idspace(self) -> None:
        """Test idspace definitions."""
        ontology = make_ad_hoc_ontology(
            _ontology="xxx",
            _idspaces={
                "go": "http://purl.obolibrary.org/obo/GO_",
            },
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            idspace: go http://purl.obolibrary.org/obo/GO_ "Gene Ontology"
            ontology: xxx
            """,
            ontology,
        )

    def test_12_xrefs_equivalent(self) -> None:
        """Test treat-xrefs-as-equivalent."""

    def test_13_xrefs_differentia(self) -> None:
        """Test treat-xrefs-as-genus-differentia."""

    def test_14_xrefs_rels(self) -> None:
        """Test treat-xrefs-as-relationship."""

    def test_15_xrefs_is_a(self) -> None:
        """Test treat-xrefs-as-is_a."""

    def test_16_remark(self) -> None:
        """Test remark."""

    def test_17_ontology(self) -> None:
        """Test ontology definition."""
        ontology = make_ad_hoc_ontology(
            _ontology="xxx",
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            ontology: xxx
            """,
            ontology,
        )

    def test_18_properties(self) -> None:
        """Test properties."""
        ontology = make_ad_hoc_ontology(
            _ontology="xxx",
            _root_terms=[default_reference("xxx", "ROOT1")],
        )
        self.assert_obo_lines(
            """\
            format-version: 1.2
            ontology: xxx
            property_value: IAO:0000700 ROOT1
            """,
            ontology,
        )
