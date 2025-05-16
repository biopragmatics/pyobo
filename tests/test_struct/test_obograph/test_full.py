"""Tests for converting OBO to OBO Graph JSON."""

import unittest
from textwrap import dedent

import obographs
from curies import Converter
from curies.vocabulary import xsd_float

from pyobo.struct import Reference, TypeDef, make_ad_hoc_ontology
from pyobo.struct.obograph import assert_graph_equal, to_parsed_obograph


class TestFull(unittest.TestCase):
    """Tests for converting OBO to OBO Graph JSON."""

    def test_typedef_1(self) -> None:
        """Test converting an OBO document with a typedef."""
        prefix_map = {
            "sssom": "https://w3id.org/sssom/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "oboInOwl": "http://www.geneontology.org/formats/oboInOwl#",
            "obo": "http://purl.obolibrary.org/obo/",
        }
        converter = Converter.from_prefix_map(prefix_map)

        obo_input = dedent("""\
            format-version: 1.4
            idspace: sssom https://w3id.org/sssom/ "Simple Standard for Sharing Ontological Mappings"
            ontology: test

            [Typedef]
            id: sssom:confidence
            range: xsd:float ! float
        """)

        expected_obograph = {
            "id": "http://purl.obolibrary.org/obo/test.owl",
            "nodes": [
                {
                    "id": "https://w3id.org/sssom/confidence",
                    "type": "PROPERTY",
                    "propertyType": "OBJECT",
                },
            ],
            "domainRangeAxioms": [
                {
                    "predicateId": "https://w3id.org/sssom/confidence",
                    "rangeClassIds": ["http://www.w3.org/2001/XMLSchema#float"],
                }
            ],
        }

        td = TypeDef(
            reference=Reference(prefix="sssom", identifier="confidence"),
            range=Reference.from_reference(xsd_float),
        )
        ontology = make_ad_hoc_ontology(
            _ontology="test",
            _typedefs=[td],
            _idspaces=prefix_map,
        )

        self.assertEqual(
            [line for line in obo_input.strip().splitlines() if line],
            [line.strip() for line in ontology.iterate_obo_lines() if line.strip()],
        )

        expected_gd = obographs.Graph.model_validate(expected_obograph)
        expected_gd_parsed = expected_gd.standardize(converter)

        assert_graph_equal(
            self,
            expected_gd_parsed,
            to_parsed_obograph(ontology).graphs[0],
        )
