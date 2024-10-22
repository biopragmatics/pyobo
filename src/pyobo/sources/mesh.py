"""Parser for the MeSH descriptors."""

import datetime
import itertools as itt
import logging
import re
from collections.abc import Collection, Iterable, Mapping
from typing import Any, Optional
from xml.etree.ElementTree import Element

from tqdm.auto import tqdm

from pyobo.api.utils import safe_get_version
from pyobo.identifier_utils import standardize_ec
from pyobo.struct import Obo, Reference, Synonym, Term
from pyobo.utils.cache import cached_json, cached_mapping
from pyobo.utils.io import parse_xml_gz
from pyobo.utils.path import ensure_path, prefix_directory_join

__all__ = [
    "MeSHGetter",
    "get_mesh_category_curies",
]

logger = logging.getLogger(__name__)

PREFIX = "mesh"
NOW_YEAR = str(datetime.datetime.now().year)
CAS_RE = re.compile(r"^\d{1,7}\-\d{2}\-\d$")
UNII_RE = re.compile(r"[0-9A-Za-z]{10}$")


class MeSHGetter(Obo):
    """An ontology representation of the Medical Subject Headings."""

    ontology = bioversions_key = PREFIX

    def _get_version(self) -> Optional[str]:
        return NOW_YEAR

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get MeSH as OBO."""
    return MeSHGetter(force=force)


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


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get MeSH OBO terms."""
    mesh_id_to_term: dict[str, Term] = {}

    descriptors = ensure_mesh_descriptors(version=version, force=force)
    supplemental_records = ensure_mesh_supplemental_records(version=version, force=force)

    for entry in itt.chain(descriptors, supplemental_records):
        identifier = entry["identifier"]
        name = entry["name"]
        definition = entry.get("scope_note")

        xrefs: list[Reference] = []
        synonyms: set[str] = set()
        for concept in entry["concepts"]:
            synonyms.add(concept["name"])
            for term in concept["terms"]:
                synonyms.add(term["name"])
            for xref_prefix, xref_identifier in concept.get("xrefs", []):
                xrefs.append(Reference(prefix=xref_prefix, identifier=xref_identifier))

        mesh_id_to_term[identifier] = Term(
            definition=definition,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            synonyms=[Synonym(name=synonym) for synonym in synonyms if synonym != name],
            xrefs=xrefs,
        )

    for entry in descriptors:
        mesh_id_to_term[entry["identifier"]].parents = [
            mesh_id_to_term[parent_descriptor_id].reference
            for parent_descriptor_id in entry["parents"]
        ]

    return mesh_id_to_term.values()


def ensure_mesh_descriptors(
    version: str, force: bool = False, force_process: bool = False
) -> list[Mapping[str, Any]]:
    """Get the parsed MeSH dictionary, and cache it if it wasn't already."""

    @cached_json(path=prefix_directory_join(PREFIX, name="desc.json", version=version), force=force)
    def _inner():
        path = ensure_path(PREFIX, url=get_descriptors_url(version), version=version)
        root = parse_xml_gz(path)
        return get_descriptor_records(root, id_key="DescriptorUI", name_key="DescriptorName/String")

    return _inner()


def get_descriptors_url(version: str) -> str:
    """Get the MeSH descriptors URL for the given version."""
    if version == NOW_YEAR:
        return f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc{version}.gz"
    return f"https://nlmpubs.nlm.nih.gov/projects/mesh/{version}/xmlmesh/desc{version}.gz"


def get_supplemental_url(version: str) -> str:
    """Get the MeSH supplemental URL for the given version."""
    if version == NOW_YEAR:
        return f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/supp{version}.gz"
    return f"https://nlmpubs.nlm.nih.gov/projects/mesh/{version}/xmlmesh/supp{version}.gz"


def ensure_mesh_supplemental_records(version: str, force: bool = False) -> list[Mapping[str, Any]]:
    """Get the parsed MeSH dictionary, and cache it if it wasn't already."""

    @cached_json(path=prefix_directory_join(PREFIX, name="supp.json", version=version), force=force)
    def _inner():
        path = ensure_path(PREFIX, url=get_supplemental_url(version), version=version)
        root = parse_xml_gz(path)
        return get_descriptor_records(
            root, id_key="SupplementalRecordUI", name_key="SupplementalRecordName/String"
        )

    return _inner()


def get_descriptor_records(element: Element, id_key: str, name_key) -> list[dict[str, Any]]:
    """Get MeSH descriptor records."""
    logger.info("extract MeSH descriptors, concepts, and terms")

    rv: list[dict[str, Any]] = [
        get_descriptor_record(descriptor, id_key=id_key, name_key=name_key)
        for descriptor in tqdm(element, desc="Getting MeSH Descriptors", unit_scale=True)
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


def get_scope_note(descriptor_record) -> Optional[str]:
    """Get the scope note from the preferred concept in a term's record."""
    if isinstance(descriptor_record, dict):
        # necessary for pre-2023 data
        concepts = descriptor_record["concepts"]
    else:
        concepts = descriptor_record
    for concept in concepts:
        scope_note = concept.get("ScopeNote")
        if scope_note is not None:
            return scope_note.replace("\\n", "\n").strip()
    return None


def get_descriptor_record(
    element: Element,
    id_key: str,
    name_key: str,
) -> dict[str, Any]:
    """Get descriptor records from the main element.

    :param element: An XML element
    :param id_key: For descriptors, set to 'DescriptorUI'. For supplement, set to 'SupplementalRecordUI'
    :param name_key: For descriptors, set to 'DescriptorName/String'.
     For supplement, set to 'SupplementalRecordName/String'
    """
    concepts = get_concept_records(element)
    scope_note = get_scope_note(concepts)
    rv = {
        "identifier": element.findtext(id_key),
        "name": element.findtext(name_key),
        "tree_numbers": sorted(
            {x.text for x in element.findall("TreeNumberList/TreeNumber") if x.text}
        ),
        "concepts": concepts,
        # TODO handle AllowableQualifiersList
    }
    if scope_note:
        rv["scope_note"] = scope_note
    return rv


def get_concept_records(element: Element) -> list[Mapping[str, Any]]:
    """Get concepts from a record."""
    return [get_concept_record(e) for e in element.findall("ConceptList/Concept")]


def _get_xrefs(element: Element) -> list[tuple[str, str]]:
    raw_registry_numbers: list[str] = sorted(
        {e.text for e in element.findall("RelatedRegistryNumberList/RegistryNumber") if e.text}
    )
    registry_number = element.findtext("RegistryNumber")
    if registry_number is not None:
        raw_registry_numbers.append(registry_number)
    raw_registry_numbers = [x for x in raw_registry_numbers if x != "0"]

    rv = []
    for registry_number in raw_registry_numbers:
        if registry_number == "0":
            continue
        elif registry_number.startswith("txid"):
            rv.append(("NCBITaxon", registry_number[4:]))
        elif registry_number.startswith("EC "):
            rv.append(("eccode", standardize_ec(registry_number[3:])))
        elif CAS_RE.fullmatch(registry_number):
            rv.append(("cas", registry_number))
        elif UNII_RE.fullmatch(registry_number):
            rv.append(("unii", registry_number))
        else:
            tqdm.write(f"Unhandled xref: {registry_number}")
    return rv


def get_concept_record(element: Element) -> Mapping[str, Any]:
    """Get a single MeSH concept record."""
    xrefs = _get_xrefs(element)

    scope_note = element.findtext("ScopeNote")
    if scope_note is not None:
        scope_note = scope_note.replace("\\n", "\n").strip()

    rv: dict[str, Any] = {
        "concept_ui": element.findtext("ConceptUI"),
        "name": element.findtext("ConceptName/String"),
        "terms": get_term_records(element),
        # TODO handle ConceptRelationList
        **element.attrib,
    }
    semantic_types = sorted(
        {x.text for x in element.findall("SemanticTypeList/SemanticType/SemanticTypeUI") if x.text}
    )
    if semantic_types:
        rv["semantic_types"] = semantic_types
    if xrefs:
        rv["xrefs"] = xrefs
    if scope_note:
        rv["ScopeNote"] = scope_note
    return rv


def get_term_records(element: Element) -> list[Mapping[str, Any]]:
    """Get all of the terms for a concept."""
    return [get_term_record(term) for term in element.findall("TermList/Term")]


def get_term_record(element) -> Mapping[str, Any]:
    """Get a single MeSH term record."""
    return {
        "term_ui": element.findtext("TermUI"),
        "name": element.findtext("String"),
        **element.attrib,
    }


def _text_or_bust(element: Element, name: str) -> str:
    n = element.findtext(name)
    if n is None:
        raise ValueError
    return n


def _get_descriptor_qualifiers(descriptor: Element) -> list[Mapping[str, str]]:
    return [
        {
            "qualifier_ui": _text_or_bust(qualifier, "QualifierUI"),
            "name": _text_or_bust(qualifier, "QualifierName/String"),
        }
        for qualifier in descriptor.findall(
            "AllowableQualifiersList/AllowableQualifier/QualifierReferredTo"
        )
    ]


def get_mesh_category_curies(
    letter: str, *, skip: Optional[Collection[str]] = None, version: Optional[str] = None
) -> list[str]:
    """Get the MeSH LUIDs for a category, by letter (e.g., "A").

    :param letter: The MeSH tree, A for anatomy, C for disease, etc.
    :param skip: An optional collection of MeSH tree codes to skip, such as "A03"
    :param version: The MeSH version to use. Defaults to latest
    :returns: A list of MeSH CURIE strings for the top level of each MeSH tree.

    .. seealso:: https://meshb.nlm.nih.gov/treeView
    """
    if version is None:
        version = safe_get_version("mesh")
    tree_to_mesh = get_tree_to_mesh_id(version=version)
    rv = []
    for i in range(1, 100):
        key = f"{letter}{i:02}"
        if skip and key in skip:
            continue
        mesh_id = tree_to_mesh.get(key)
        if mesh_id is None:
            break
        rv.append(f"mesh:{mesh_id}")
    return rv


if __name__ == "__main__":
    get_obo(force=True).write_default(force=True, write_obo=True)
