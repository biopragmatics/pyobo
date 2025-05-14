"""Test conversion from OBO to OFN."""

import json
import tempfile
import unittest
from pathlib import Path

import curies
import obographs
from bioontologies import robot
from curies import vocabulary as v

from pyobo.struct import (
    Reference,
    SynonymTypeDef,
    Term,
    default_reference,
    make_ad_hoc_ontology,
)
from pyobo.struct.obograph.export import to_parsed_obograph

EXPECTED_RAW_OBOGRAPH = {
    "graphs": [
        {
            "id": "http://purl.obolibrary.org/obo/go.owl",
            "meta": {
                "basicPropertyValues": [
                    {
                        "pred": "http://purl.obolibrary.org/obo/IAO_0000700",
                        "val": "http://purl.obolibrary.org/obo/GO_1234567",
                    },
                    {
                        "pred": "http://purl.org/dc/terms/description",
                        "val": "The Gene Ontology project provides a controlled vocabulary to describe gene and gene product attributes in any organism.",
                    },
                    {"pred": "http://purl.org/dc/terms/license", "val": "CC-BY-4.0"},
                    {"pred": "http://purl.org/dc/terms/title", "val": "Gene Ontology"},
                    {
                        "pred": "http://www.geneontology.org/formats/oboInOwl#auto-generated-by",
                        "val": "PyOBO",
                    },
                    {
                        "pred": "http://www.geneontology.org/formats/oboInOwl#hasOBOFormatVersion",
                        "val": "1.4",
                    },
                ],
                "version": "http://purl.obolibrary.org/obo/go/30/go.owl",
            },
            "nodes": [
                {
                    "id": "http://purl.obolibrary.org/obo/GO_1234567",
                    "lbl": "test",
                    "type": "CLASS",
                    "meta": {
                        "subsets": ["http://purl.obolibrary.org/obo/go#SUBSET-1"],
                        "synonyms": [
                            {"pred": "hasExactSynonym", "val": "test-synonym-3"},
                            {"pred": "hasRelatedSynonym", "val": "test-synonym-1"},
                            {
                                "synonymType": "http://purl.obolibrary.org/obo/OMO_0003008",
                                "pred": "hasRelatedSynonym",
                                "val": "test-synonym-2",
                            },
                            {
                                "synonymType": "http://purl.obolibrary.org/obo/OMO_0003008",
                                "pred": "hasRelatedSynonym",
                                "val": "test-synonym-4",
                            },
                        ],
                    },
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#SubsetProperty",
                    "lbl": "subset_property",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#SynonymTypeProperty",
                    "lbl": "synonym_type_property",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#auto-generated-by",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym",
                    "lbl": "has_exact_synonym",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#hasOBOFormatVersion",
                    "lbl": "has_obo_format_version",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#hasRelatedSynonym",
                    "lbl": "has_related_synonym",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#hasSynonymType",
                    "lbl": "has_synonym_type",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#id",
                    "lbl": "id",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.geneontology.org/formats/oboInOwl#inSubset",
                    "lbl": "in_subset",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.w3.org/2000/01/rdf-schema#comment",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {
                    "id": "http://www.w3.org/2000/01/rdf-schema#label",
                    "type": "PROPERTY",
                    "propertyType": "ANNOTATION",
                },
                {"id": "http://purl.obolibrary.org/obo/OMO_0003008", "lbl": "previous name"},
                {
                    "id": "http://purl.obolibrary.org/obo/go#SUBSET-1",
                    "meta": {"comments": ["test subset 1"]},
                },
            ],
        }
    ]
}


class TestConversion(unittest.TestCase):
    """Test conversion from OBO to OFN."""

    def test_simple_conversion(self) -> None:
        """Test conversion."""
        subset = default_reference("go", "SUBSET-1")
        synonym_typedef = SynonymTypeDef(reference=v.previous_name)
        term = Term(
            reference=Reference(prefix="go", identifier="1234567", name="test"),
            subsets=[subset],
        )
        term.append_synonym("test-synonym-1")
        term.append_synonym("test-synonym-2", type=synonym_typedef)
        term.append_synonym("test-synonym-3", specificity="EXACT")
        term.append_synonym("test-synonym-4", type=synonym_typedef, language="en")

        obo_ontology = make_ad_hoc_ontology(
            _ontology="go",
            _name="Gene Ontology",
            _data_version="30",
            _auto_generated_by="PyOBO",
            terms=[term],
            _subsetdefs=[(subset, "test subset 1")],
            _synonym_typedefs=[synonym_typedef],
            _root_terms=[term.reference],
            _idspaces={
                "GO": "http://purl.obolibrary.org/obo/GO_",
            },
        )

        converter = curies.Converter.from_prefix_map(
            {
                "go": "http://purl.obolibrary.org/obo/GO_",
                "omo": "http://purl.obolibrary.org/obo/OMO_",
                "oboinowl": "http://www.geneontology.org/formats/oboInOwl#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "dcterms": "http://purl.org/dc/terms/",
            }
        )
        with tempfile.TemporaryDirectory() as d:
            obo_path = Path(d).joinpath("output.obo")
            obo_ontology.write_obo(obo_path)

            json_path = Path(d).joinpath("output.json")
            robot.convert(obo_path, json_path)

            j = json.loads(json_path.read_text())

            self.assertEqual(EXPECTED_RAW_OBOGRAPH, j)

            m = obographs.GraphDocument.model_validate(j)

            self.assertEqual(
                m.model_dump(), to_parsed_obograph(obo_ontology, converter).model_dump()
            )
