# -*- coding: utf-8 -*-

"""Converter for WikiPathways."""

import logging
from typing import Iterable, List, Tuple

from ..constants import SPECIES_REMAPPING
from ..path_utils import ensure_path
from ..struct import Obo, Reference, Term, from_species
from ..struct.defs import pathway_has_part

logger = logging.getLogger(__name__)

PREFIX = 'wikipathways'
DATA_VERSION = '20200310'
BASE_URL = f'http://data.wikipathways.org/{DATA_VERSION}/gmt/wikipathways-{DATA_VERSION}-gmt'

_PATHWAY_INFO = [
    ('Anopheles_gambiae', '7165'),
    ('Arabidopsis_thaliana', '3702'),
    ('Bos_taurus', '9913'),
    ('Caenorhabditis_elegans', '6239'),
    ('Canis_familiaris', '9615'),
    ('Danio_rerio', '7955'),
    ('Drosophila_melanogaster', '7227'),
    ('Equus_caballus', '9796'),
    ('Gallus_gallus', '9031'),
    ('Homo_sapiens', '9606'),
    ('Mus_musculus', '10090'),
    ('Oryza_sativa', '4530'),
    ('Pan_troglodytes', '9598'),
    ('Populus_trichocarpa', '3694'),
    ('Rattus_norvegicus', '10116'),
    ('Saccharomyces_cerevisiae', '4932'),
    ('Sus_scrofa', '9823'),
]

GMTSummary = Tuple[str, str, str, List[str]]


def get_obo() -> Obo:
    """Get WikiPathways as OBO."""
    return Obo(
        ontology=PREFIX,
        name='WikiPathways',
        data_version=DATA_VERSION,
        iter_terms=iter_terms,
        typedefs=[pathway_has_part, from_species],
    )


def iter_terms() -> Iterable[Term]:
    """Get WikiPathways terms."""
    for species_code, tax_id in _PATHWAY_INFO:
        url = f'{BASE_URL}-{species_code}.gmt'
        path = ensure_path(PREFIX, url, version=DATA_VERSION)

        species_code = species_code.replace('_', ' ')
        species_reference = Reference(
            prefix='taxonomy',
            identifier=tax_id,
            name=SPECIES_REMAPPING.get(species_code, species_code),
        )

        for name, _, identifier, genes in parse_gmt_file(path):
            term = Term(reference=Reference(prefix=PREFIX, identifier=identifier, name=name))
            term.append_relationship(from_species, species_reference)
            for ncbigene_id in genes:
                term.append_relationship(pathway_has_part, Reference(prefix='ncbigene', identifier=ncbigene_id))
            yield term


def parse_gmt_file(path: str) -> List[GMTSummary]:
    """Return file as list of pathway - gene sets (ENTREZ-identifiers).

    :param path: path to GMT file
    :return: line-based processed file
    """
    with open(path) as file:
        return [
            _process_line(line)
            for line in file
        ]


def _process_line(line: str) -> GMTSummary:
    """Return the pathway name, species, url, and gene sets associated.

    :param line: gmt file line
    :return: pathway name
    :return: pathway species
    :return: pathway info url
    :return: genes set associated
    """
    name_species, identifier, *genes = [
        word.strip()
        for word in line.split('\t')
    ]

    return (
        _get_pathway_name(name_species),
        _get_pathway_species(name_species),
        _process_pathway_id(_get_pathway_id(identifier)),
        genes,
    )


def _process_pathway_id(pathway_id: str) -> str:
    """Process the pathway id.

    :param pathway_id: pathway id with suffix
    :return: processed pathway id
    """
    return pathway_id.split('_')[0]


def _get_pathway_name(line: str) -> str:
    """Split the pathway name word and returns the name.

    :param line: first word from gmt file
    :return: pathway name
    """
    return line.split('%')[0]


def _get_pathway_species(line: str) -> str:
    return line.split('%')[-1]


def _get_pathway_id(pathway_info_url: str) -> str:
    """Split the pathway info url and returns the id.

    :param pathway_info_url: first word from gmt file
    :return: pathway id
    """
    return pathway_info_url.replace('http://www.wikipathways.org/instance/', '')


if __name__ == '__main__':
    get_obo().write_default()
