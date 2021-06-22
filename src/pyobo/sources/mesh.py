# -*- coding: utf-8 -*-

"""Parser for the MeSH descriptors."""

import itertools as itt
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional
from xml.etree.ElementTree import Element

import bioversions
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, Term
from ..utils.cache import cached_json, cached_mapping
from ..utils.io import parse_xml_gz
from ..utils.path import ensure_path, prefix_directory_join

logger = logging.getLogger(__name__)

PREFIX = "mesh"


def get_obo() -> Obo:
    """Get MeSH as OBO."""
    version = bioversions.get_version("mesh")
    return Obo(
        ontology=PREFIX,
        name="Medical Subject Headings",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(version=version),
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_tree_to_mesh_id(version: str) -> Mapping[str, str]:
    """Get a mapping from MeSH tree numbers to their MeSH identifiers."""

    @cached_mapping(
        path=prefix_directory_join(PREFIX, name="mesh_tree.tsv", version=version),
        header=["mesh_tree_number", "mesh_id"],
    )
    def _inner():
        mesh = ensure_mesh_descriptors(version=version)
        rv = {}
        for entry in mesh:
            mesh_id = entry["identifier"]
            for tree_number in entry["tree_numbers"]:
                rv[tree_number] = mesh_id
        return rv

    return _inner()


def get_terms(version: str) -> Iterable[Term]:
    """Get MeSH OBO terms."""
    mesh_id_to_term: Dict[str, Term] = {}

    descriptors = ensure_mesh_descriptors(version=version)
    supplemental_records = ensure_mesh_supplemental_records(version=version)

    for entry in itt.chain(descriptors, supplemental_records):
        identifier = entry["identifier"]
        name = entry["name"]
        definition = (get_scope_note(entry) or "").strip()

        synonyms = set()
        for concept in entry["concepts"]:
            synonyms.add(concept["name"])
            for term in concept["terms"]:
                synonyms.add(term["name"])
        synonyms = [Synonym(name=synonym) for synonym in synonyms if synonym != name]

        mesh_id_to_term[identifier] = Term(
            definition=definition,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            synonyms=synonyms,
        )

    for entry in descriptors:
        mesh_id_to_term[entry["identifier"]].parents = [
            mesh_id_to_term[parent_descriptor_id].reference
            for parent_descriptor_id in entry["parents"]
        ]

    return mesh_id_to_term.values()


def ensure_mesh_descriptors(version: str) -> List[Mapping[str, Any]]:
    """Get the parsed MeSH dictionary, and cache it if it wasn't already."""

    @cached_json(path=prefix_directory_join(PREFIX, name="mesh.json", version=version))
    def _inner():
        url = f"ftp://nlmpubs.nlm.nih.gov/online/mesh/{version}/xmlmesh/desc{version}.gz"
        path = ensure_path(PREFIX, url=url, version=version)
        root = parse_xml_gz(path)
        return get_descriptor_records(root, id_key="DescriptorUI", name_key="DescriptorName/String")

    return _inner()


def ensure_mesh_supplemental_records(version: str) -> List[Mapping[str, Any]]:
    """Get the parsed MeSH dictionary, and cache it if it wasn't already."""

    @cached_json(path=prefix_directory_join(PREFIX, name="supp.json", version=version))
    def _inner():
        url = f"ftp://nlmpubs.nlm.nih.gov/online/mesh/{version}/xmlmesh/supp{version}.gz"
        path = ensure_path(PREFIX, url=url, version=version)
        root = parse_xml_gz(path)
        return get_descriptor_records(
            root, id_key="SupplementalRecordUI", name_key="SupplementalRecordName/String"
        )

    return _inner()


def get_descriptor_records(element: Element, id_key: str, name_key) -> List[Mapping]:
    """Get MeSH descriptor records."""
    logger.info("extract MeSH descriptors, concepts, and terms")

    rv = [
        get_descriptor_record(descriptor, id_key=id_key, name_key=name_key)
        for descriptor in tqdm(element, desc="Getting MeSH Descriptors")
    ]
    logger.debug(f"got {len(rv)} descriptors")

    # cache tree numbers
    tree_number_to_descriptor_ui = {
        tree_number: descriptor["identifier"]
        for descriptor in rv
        for tree_number in descriptor["tree_numbers"]
    }
    logger.debug(f"got {len(tree_number_to_descriptor_ui)} tree mappings")

    # add in parents to each descriptor based on their tree numbers
    for descriptor in rv:
        parents_descriptor_uis = set()
        for tree_number in descriptor["tree_numbers"]:
            try:
                parent_tn, self_tn = tree_number.rsplit(".", 1)
            except ValueError:
                logger.debug("No dot for %s", tree_number)
                continue

            parent_descriptor_ui = tree_number_to_descriptor_ui.get(parent_tn)
            if parent_descriptor_ui is not None:
                parents_descriptor_uis.add(parent_descriptor_ui)
            else:
                logger.debug("missing tree number: %s", parent_tn)

        descriptor["parents"] = list(parents_descriptor_uis)

    return rv


def get_scope_note(term) -> Optional[str]:
    """Get the scope note from the preferred concept in a term's record."""
    for concept in term["concepts"]:
        if "ScopeNote" in concept:
            return concept["ScopeNote"]


def get_descriptor_record(
    element: Element,
    id_key: str,
    name_key: str,
) -> Dict[str, Any]:
    """Get descriptor records from the main element.

    :param element: An XML element
    :param id_key: For descriptors, set to 'DescriptorUI'. For supplement, set to 'SupplementalRecordUI'
    :param name_key: For descriptors, set to 'DescriptorName/String'.
     For supplement, set to 'SupplementalRecordName/String'
    """
    return {
        "identifier": element.findtext(id_key),
        "name": element.findtext(name_key),
        "tree_numbers": sorted({x.text for x in element.findall("TreeNumberList/TreeNumber")}),
        "concepts": get_concept_records(element),
        # TODO handle AllowableQualifiersList
        # TODO add ScopeNote as description
    }


def get_concept_records(element: Element) -> List[Mapping[str, Any]]:
    """Get concepts from a record."""
    return [get_concept_record(concept) for concept in element.findall("ConceptList/Concept")]


def get_concept_record(concept):
    """Get a single MeSH concept record."""
    return {
        "concept_ui": concept.findtext("ConceptUI"),
        "name": concept.findtext("ConceptName/String"),
        "semantic_types": list(
            {x.text for x in concept.findall("SemanticTypeList/SemanticType/SemanticTypeUI")}
        ),
        "ScopeNote": concept.findtext("ScopeNote"),
        "terms": get_term_records(concept),
        # TODO handle ConceptRelationList
        **concept.attrib,
    }


def get_term_records(element: Element) -> List[Mapping[str, Any]]:
    """Get all of the terms for a concept."""
    return [get_term_record(term) for term in element.findall("TermList/Term")]


def get_term_record(term):
    """Get a single MeSH term record."""
    return {
        "term_ui": term.findtext("TermUI"),
        "name": term.findtext("String"),
        **term.attrib,
    }


def _get_descriptor_qualifiers(descriptor: Element) -> List[Mapping[str, str]]:
    return [
        {
            "qualifier_ui": qualifier.findtext("QualifierUI"),
            "name": qualifier.findtext("QualifierName/String"),
        }
        for qualifier in descriptor.findall(
            "AllowableQualifiersList/AllowableQualifier/QualifierReferredTo"
        )
    ]


if __name__ == "__main__":
    get_obo().write_default()
