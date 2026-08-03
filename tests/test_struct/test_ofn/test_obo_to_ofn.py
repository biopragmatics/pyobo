"""Test conversion from OBO to OFN."""

from textwrap import dedent

from curies import vocabulary as v

from pyobo import build_ontology
from pyobo.struct import Obo, Reference, SynonymTypeDef, Term, default_reference
from pyobo.struct.functional import get_ofn_from_obo
from tests import cases

R1 = Reference(prefix="GO", identifier="0032571", name="response to vitamin K")


class TestConversion(cases.TestMixin):
    """Test conversion from OBO to OFN."""

    def assert_ontology_ofn(self, obo_ontology: Obo, ofn: str) -> None:
        """Assert an OBO ontology."""
        ofn_ontology = get_ofn_from_obo(obo_ontology)
        self.assertEqual(dedent(ofn).strip(), ofn_ontology.to_funowl().strip())

    def test_0_id(self) -> None:
        """Test a term."""
        self.maxDiff = None
        term = Term(reference=Reference.from_reference(R1.without_name()))
        obo = build_ontology(prefix="go", terms=[term])
        self.assert_ontology_ofn(
            obo,
            """\

        Prefix(dcterms:=<http://purl.org/dc/terms/>)
        Prefix(doap:=<http://usefulinc.com/ns/doap#>)
        Prefix(foaf:=<http://xmlns.com/foaf/0.1/>)
        Prefix(GO:=<http://purl.obolibrary.org/obo/GO_>)
        Prefix(orcid:=<https://orcid.org/>)
        Prefix(owl:=<http://www.w3.org/2002/07/owl#>)
        Prefix(rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>)
        Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
        Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)

        Ontology(<https://w3id.org/biopragmatics/resources/go/go.ofn>
        Annotation(dcterms:title "Gene Ontology"^^xsd:string)
        Annotation(dcterms:license "CC-BY-4.0"^^xsd:string)
        Annotation(dcterms:description "The Gene Ontology project provides a controlled vocabulary to describe gene and gene product attributes in any organism."^^xsd:string)
        Annotation(foaf:homepage "http://geneontology.org/"^^xsd:anyURI)
        Annotation(doap:repository "https://github.com/geneontology/go-ontology"^^xsd:anyURI)
        Annotation(foaf:logo "https://obofoundry.org/images/go_logo.png"^^xsd:anyURI)
        Annotation(doap:maintainer orcid:0000-0001-6787-2901)

        Declaration(Class(GO:0032571))
        )
        """,
        )

    def test_simple_conversion(self) -> None:
        """Test conversion."""
        subset = default_reference("go", "SUBSET-1")
        synonym_typedef = SynonymTypeDef(reference=Reference.from_reference(v.previous_name))
        term = Term(reference=R1, subsets=[subset])
        term.append_synonym("test-synonym-1")
        term.append_synonym("test-synonym-2", type=synonym_typedef)
        term.append_synonym("test-synonym-3", specificity="EXACT")
        term.append_synonym("test-synonym-4", type=synonym_typedef, language="en")

        obo_ontology = build_ontology(
            prefix="go",
            name="Gene Ontology",
            version="30",
            auto_generated_by="PyOBO",
            terms=[term],
            subsetdefs={subset: "test subset 1"},
            synonym_typedefs=[synonym_typedef],
            root_terms=[term.reference],
            idspaces={
                "GO": "http://purl.obolibrary.org/obo/GO_",
            },
        )
        self.assert_ontology_ofn(
            obo_ontology,
            """\
                Prefix(dcterms:=<http://purl.org/dc/terms/>)
                Prefix(doap:=<http://usefulinc.com/ns/doap#>)
                Prefix(foaf:=<http://xmlns.com/foaf/0.1/>)
                Prefix(GO:=<http://purl.obolibrary.org/obo/GO_>)
                Prefix(IAO:=<http://purl.obolibrary.org/obo/IAO_>)
                Prefix(obo:=<http://purl.obolibrary.org/obo/>)
                Prefix(oboInOwl:=<http://www.geneontology.org/formats/oboInOwl#>)
                Prefix(OMO:=<http://purl.obolibrary.org/obo/OMO_>)
                Prefix(orcid:=<https://orcid.org/>)
                Prefix(owl:=<http://www.w3.org/2002/07/owl#>)
                Prefix(rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>)
                Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
                Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)

                Ontology(<https://w3id.org/biopragmatics/resources/go/go.ofn> <https://w3id.org/biopragmatics/resources/go/30/go.ofn>
                Annotation(dcterms:title "Gene Ontology"^^xsd:string)
                Annotation(dcterms:license "CC-BY-4.0"^^xsd:string)
                Annotation(dcterms:description "The Gene Ontology project provides a controlled vocabulary to describe gene and gene product attributes in any organism."^^xsd:string)
                Annotation(foaf:homepage "http://geneontology.org/"^^xsd:anyURI)
                Annotation(doap:repository "https://github.com/geneontology/go-ontology"^^xsd:anyURI)
                Annotation(foaf:logo "https://obofoundry.org/images/go_logo.png"^^xsd:anyURI)
                Annotation(doap:maintainer orcid:0000-0001-6787-2901)
                Annotation(IAO:0000700 GO:0032571)
                Annotation(owl:versionInfo "30"^^xsd:string)
                Annotation(oboInOwl:auto-generated-by "PyOBO"^^xsd:string)

                Declaration(AnnotationProperty(IAO:0000700))
                AnnotationAssertion(rdfs:label IAO:0000700 "has ontology root term")
                Declaration(AnnotationProperty(oboInOwl:SubsetProperty))
                Declaration(AnnotationProperty(obo:go#SUBSET-1))
                AnnotationAssertion(rdfs:label obo:go#SUBSET-1 "test subset 1")
                SubAnnotationPropertyOf(obo:go#SUBSET-1 oboInOwl:SubsetProperty)
                Declaration(AnnotationProperty(OMO:0003008))
                AnnotationAssertion(rdfs:label OMO:0003008 "previous name")
                SubAnnotationPropertyOf(OMO:0003008 oboInOwl:SynonymTypeProperty)
                Declaration(Class(GO:0032571))
                AnnotationAssertion(rdfs:label GO:0032571 "response to vitamin K")
                AnnotationAssertion(oboInOwl:inSubset GO:0032571 obo:go#SUBSET-1)
                AnnotationAssertion(oboInOwl:hasRelatedSynonym GO:0032571 "test-synonym-1")
                AnnotationAssertion(Annotation(oboInOwl:hasSynonymType OMO:0003008) oboInOwl:hasRelatedSynonym GO:0032571 "test-synonym-2")
                AnnotationAssertion(oboInOwl:hasExactSynonym GO:0032571 "test-synonym-3")
                AnnotationAssertion(Annotation(oboInOwl:hasSynonymType OMO:0003008) oboInOwl:hasRelatedSynonym GO:0032571 "test-synonym-4"@en)
                )
            """,
        )
