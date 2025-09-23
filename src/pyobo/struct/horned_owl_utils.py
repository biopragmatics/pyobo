"""PyHornedOWl reads RDF-XML and OWL-XML files."""

import pyhornedowl

from pathlib import Path
from .struct import Obo, Term, Reference, make_ad_hoc_ontology


def load(path: str) -> Obo:
    """Load an ontology."""
    ontology: pyhornedowl.PyIndexedOntology = pyhornedowl.open_ontology_from_file(path)

    iri = ontology.get_iri()
    version_iri = ontology.get_version_iri()

    for c in ontology.get_object_properties():
        print(c)

    ontology.get_iri_for_label()

    for c in ontology.get_annotation_properties():
        print(c, ontology.get_iri_for_label())

    # for c in ontology.get_classes():
    #     print(c)

    # for a in ontology.get_axioms():
    #     print(a)





    # what about get annotation properties and data properties?


if __name__ == '__main__':
    load("/Users/cthoyt/dev/obo-db-ingest/export/ec/ec.owl")
    # load("/Users/cthoyt/Downloads/fbbt.owl")
