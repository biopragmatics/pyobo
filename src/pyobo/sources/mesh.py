# -*- coding: utf-8 -*-

"""Parser for the MeSH descriptors."""

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional
from xml.etree.ElementTree import Element

from tqdm import tqdm

from pyobo import Obo, Reference, Synonym, Term
from pyobo.sources.utils import parse_xml_gz
from pyobo.utils import ensure_path, get_prefix_directory

logger = logging.getLogger(__name__)

PREFIX = 'mesh'
YEAR = '2019'
DESCRIPTOR_URL = f'ftp://nlmpubs.nlm.nih.gov/online/mesh/{YEAR}/xmlmesh/desc{YEAR}.gz'


def get_obo() -> Obo:
    """Get MeSH as OBO."""
    terms = list(get_terms())
    return Obo(
        ontology=PREFIX,
        terms=terms,
        data_version=YEAR,
    )


def get_terms() -> Iterable[Term]:
    """Get MeSH OBO terms."""
    mesh = ensure_mesh()
    mesh_id_to_term: Dict[str, Term] = {}
    for entry in mesh:
        identifier = entry['descriptor_ui']
        name = entry['name']
        definition = (get_scope_note(entry) or '').strip()

        synonyms = set()
        for concept in entry['concepts']:
            synonyms.add(concept['name'])
            for term in concept['terms']:
                synonyms.add(term['name'])
        synonyms = [
            Synonym(name=synonym)
            for synonym in synonyms
            if synonym != name
        ]

        mesh_id_to_term[identifier] = Term(
            name=name,
            definition=definition,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            synonyms=synonyms,
        )

    for entry in mesh:
        mesh_id_to_term[entry['descriptor_ui']].parents = [
            mesh_id_to_term[parent_descriptor_id].reference
            for parent_descriptor_id in entry['parents']
        ]

    return mesh_id_to_term.values()


def ensure_mesh() -> List[Mapping[str, Any]]:
    """Get the parsed MeSH dictionary, and cache it if it wasn't already."""
    mesh_json_path = os.path.join(get_prefix_directory(PREFIX), f'mesh_{YEAR}.json')
    if os.path.exists(mesh_json_path):
        with open(mesh_json_path) as file:
            return json.load(file)

    path = ensure_path(PREFIX, DESCRIPTOR_URL)
    root = parse_xml_gz(path)
    rv = get_descriptor_records(root)

    with open(mesh_json_path, 'w') as file:
        json.dump(rv, file, indent=2)

    return rv


def get_descriptor_records(element: Element) -> List[Mapping]:
    """Get MeSH descriptor records."""
    logger.info('extract MeSH descriptors, concepts, and terms')

    rv = [
        get_descriptor_record(descriptor)
        for descriptor in tqdm(element, desc='Getting MeSH Descriptors')
    ]
    logger.debug(f'got {len(rv)} descriptors')

    # cache tree numbers
    tree_number_to_descriptor_ui = {
        tree_number: descriptor['descriptor_ui']
        for descriptor in rv
        for tree_number in descriptor['tree_numbers']
    }
    logger.debug(f'got {len(tree_number_to_descriptor_ui)} tree mappings')

    # add in parents to each descriptor based on their tree numbers
    for descriptor in rv:
        parents_descriptor_uis = set()
        for tree_number in descriptor['tree_numbers']:
            try:
                parent_tn, self_tn = tree_number.rsplit('.', 1)
            except ValueError:
                logger.debug('No dot for %s', tree_number)
                continue

            parent_descriptor_ui = tree_number_to_descriptor_ui.get(parent_tn)
            if parent_descriptor_ui is not None:
                parents_descriptor_uis.add(parent_descriptor_ui)
            else:
                logger.debug('missing tree number: %s', parent_tn)

        descriptor['parents'] = list(parents_descriptor_uis)

    return rv


def get_scope_note(term) -> Optional[str]:
    """Get the scope note from the preferred concept in a term's record."""
    for concept in term['concepts']:
        if 'ScopeNote' in concept:
            return concept['ScopeNote']


def get_descriptor_record(element: Element) -> Dict[str, Any]:
    """Get descriptor records from the main element."""
    return {
        'descriptor_ui': element.findtext('DescriptorUI'),
        'name': element.findtext('DescriptorName/String'),
        'tree_numbers': sorted({
            x.text
            for x in element.findall('TreeNumberList/TreeNumber')
        }),
        'concepts': get_concept_records(element),
        # TODO handle AllowableQualifiersList
        # TODO add ScopeNote as description
    }


def get_concept_records(element: Element) -> List[Mapping[str, Any]]:
    """Get concepts from a record."""
    return [
        get_concept_record(concept)
        for concept in element.findall('ConceptList/Concept')
    ]


def get_concept_record(concept):
    """Get a single MeSH concept record."""
    return {
        'concept_ui': concept.findtext('ConceptUI'),
        'name': concept.findtext('ConceptName/String'),
        'semantic_types': list({
            x.text
            for x in concept.findall('SemanticTypeList/SemanticType/SemanticTypeUI')
        }),
        'ScopeNote': concept.findtext('ScopeNote'),
        'terms': get_term_records(concept),
        # TODO handle ConceptRelationList
        **concept.attrib,
    }


def get_term_records(element: Element) -> List[Mapping[str, Any]]:
    """Get all of the terms for a concept."""
    return [
        get_term_record(term)
        for term in element.findall('TermList/Term')
    ]


def get_term_record(term):
    """Get a single MeSH term record."""
    return {
        'term_ui': term.findtext('TermUI'),
        'name': term.findtext('String'),
        **term.attrib,
    }


def _get_descriptor_qualifiers(descriptor: Element) -> List[Mapping[str, str]]:
    return [
        {
            'qualifier_ui': qualifier.findtext('QualifierUI'),
            'name': qualifier.findtext('QualifierName/String'),
        }
        for qualifier in descriptor.findall('AllowableQualifiersList/AllowableQualifier/QualifierReferredTo')
    ]


if __name__ == '__main__':
    get_obo().write_default()
