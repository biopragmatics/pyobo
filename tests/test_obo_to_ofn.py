"""Test conversion from OBO to OFN."""

import unittest
from textwrap import dedent

from curies import vocabulary as v

from pyobo.struct import (
    Reference,
    SynonymTypeDef,
    Term,
    default_reference,
    make_ad_hoc_ontology,
)
from pyobo.struct.functional.obo_to_functional import get_ofn_from_obo


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

        obo_ontology = make_ad_hoc_ontology(
            _ontology="go",
            _name="Gene Ontology",
            terms=[term],
            _subsetdefs=[(subset, "test subset 1")],
            _synonym_typedefs=[synonym_typedef],
            _root_terms=[term.reference],
            _idspaces={
                "GO": "http://purl.obolibrary.org/obo/GO_",
            },
        )
        ofn_ontology = get_ofn_from_obo(obo_ontology)
        self.assertEqual(
            dedent("""\
                Prefix( dcterms:=<http://purl.org/dc/terms/> )
                Prefix( GO:=<http://purl.obolibrary.org/obo/GO_> )
                Prefix( oboInOwl:=<http://www.geneontology.org/formats/oboInOwl#> )
                Prefix( OMO:=<http://purl.obolibrary.org/obo/OMO_> )
                Prefix( owl:=<http://www.w3.org/2002/07/owl#> )
                Prefix( rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#> )
                Prefix( rdfs:=<http://www.w3.org/2000/01/rdf-schema#> )
                Prefix( semapv:=<https://w3id.org/semapv/vocab/> )
                Prefix( skos:=<http://www.w3.org/2004/02/skos/core#> )
                Prefix( sssom:=<https://w3id.org/sssom/> )
                Prefix( xsd:=<http://www.w3.org/2001/XMLSchema#> )

                Ontology(<go>
                  Annotation( dcterms:title "Gene Ontology"^^xsd:string )
                  Annotation( dcterms:license "CC-BY-4.0"^^xsd:string )
                  Annotation( dcterms:description "The Gene Ontology project provides a controlled vocabulary to describe gene and gene product attributes in any organism."^^xsd:string )
                  Annotation( IAO:0000700 GO:1234567 )

                  Declaration( AnnotationProperty( IAO:0000700 ) )
                  AnnotationAssertion( rdfs:label IAO:0000700 "has ontology root term" )
                  Declaration( AnnotationProperty( oboInOwl:SubsetProperty ) )
                  Declaration( AnnotationProperty( obo:go#SUBSET-1 ) )
                  AnnotationAssertion( rdfs:label obo:go#SUBSET-1 "test subset 1" )
                  SubAnnotationPropertyOf( obo:go#SUBSET-1 oboInOwl:SubsetProperty )
                  Declaration( AnnotationProperty( oboInOwl:hasScope ) )
                  Declaration( AnnotationProperty( OMO:0003008 ) )
                  AnnotationAssertion( rdfs:label OMO:0003008 "previous name" )
                  SubAnnotationPropertyOf( OMO:0003008 oboInOwl:SynonymTypeProperty )
                  Declaration( Class( GO:1234567 ) )
                  AnnotationAssertion( rdfs:label GO:1234567 "test" )
                  AnnotationAssertion( oboInOwl:inSubset GO:1234567 obo:go#SUBSET-1 )
                  AnnotationAssertion( oboInOwl:hasExactSynonym GO:1234567 "test-synonym-1" )
                  AnnotationAssertion( Annotation( oboInOwl:hasSynonymType OMO:0003008 ) oboInOwl:hasExactSynonym GO:1234567 "test-synonym-2" )
                )
            """).strip(),
            ofn_ontology.to_funowl().strip(),
        )