# -*- coding: utf-8 -*-

"""Converter for WikiPathways."""

import logging
from typing import Iterable

import bioversions

from .gmt_utils import parse_wikipathways_gmt
from ..constants import SPECIES_REMAPPING
from ..path_utils import ensure_path
from ..struct import Obo, Reference, Term, from_species
from ..struct.typedef import has_part

logger = logging.getLogger(__name__)

PREFIX = 'wikipathways'

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


def get_obo() -> Obo:
    """Get WikiPathways as OBO."""
    version = bioversions.get_version('wikipathways')
    return Obo(
        ontology=PREFIX,
        name='WikiPathways',
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        typedefs=[has_part, from_species],
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Get WikiPathways terms."""
    base_url = f'http://data.wikipathways.org/{version}/gmt/wikipathways-{version}-gmt'

    for species_code, taxonomy_id in _PATHWAY_INFO:
        url = f'{base_url}-{species_code}.gmt'
        path = ensure_path(PREFIX, url=url, version=version)

        species_code = species_code.replace('_', ' ')
        species_reference = Reference(
            prefix='ncbitaxon',
            identifier=taxonomy_id,
            name=SPECIES_REMAPPING.get(species_code, species_code),
        )

        for identifier, _version, _revision, name, _species, genes in parse_wikipathways_gmt(path):
            term = Term(reference=Reference(prefix=PREFIX, identifier=identifier, name=name))
            term.append_relationship(from_species, species_reference)
            for ncbigene_id in genes:
                term.append_relationship(has_part, Reference(prefix='ncbigene', identifier=ncbigene_id))
            yield term


if __name__ == '__main__':
    get_obo().write_default()
