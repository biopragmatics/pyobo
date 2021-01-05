# -*- coding: utf-8 -*-

"""Convert KEGG Genome to OBO.

Run with ``python -m pyobo.sources.kegg.genome``
"""

import logging
from typing import Iterable

import click
from more_click import verbose_option
from tqdm import tqdm

import pyobo
from pyobo.sources.kegg.api import KEGGGenome, KEGG_GENOME_PREFIX, ensure_list_genomes
from pyobo.struct import Obo, Reference, Term

logger = logging.getLogger(__name__)


def _s(line: str, sep: str):
    return [part.strip() for part in line.strip().split(sep, 1)]


def get_obo() -> Obo:
    """Get KEGG Genome as OBO."""
    return Obo(
        ontology=KEGG_GENOME_PREFIX,
        iter_terms=iter_terms,
        name='KEGG Genome',
        auto_generated_by=f'bio2obo:{KEGG_GENOME_PREFIX}',
    )


def parse_genome_line(line: str) -> KEGGGenome:
    """Parse a line from the KEGG Genome database."""
    line = line.strip()
    identifier, rest = _s(line, '\t')
    identifier = identifier[len('gn:'):]
    if ';' in rest:
        rest, name = _s(rest, ';')

        rest = [part.strip() for part in rest.split(',')]
        if len(rest) == 3:
            kegg_code, long_code, taxonomy_id = rest
        elif len(rest) == 2:
            kegg_code, taxonomy_id = rest
            long_code = None
        else:
            raise ValueError
    else:
        name = rest
        taxonomy_id = None
        long_code = None
        kegg_code = None

    if '\t' in name:
        logger.warning('tab in name: %s', name)
        name = name.replace('\t', ' ')

    return KEGGGenome(
        identifier=identifier,
        code=kegg_code,
        long_code=long_code,
        taxonomy_id=taxonomy_id,
        name=name,
    )


def iter_kegg_genomes() -> Iterable[KEGGGenome]:
    """Iterate over all KEGG genomes."""
    path = ensure_list_genomes()
    with open(path) as file:
        lines = [line.strip() for line in file]
    for line in tqdm(lines, desc='KEGG Genomes'):
        yield parse_genome_line(line)


def iter_terms() -> Iterable[Term]:
    """Iterate over terms for KEGG Genome."""
    errors = 0
    for kegg_genome in iter_kegg_genomes():
        xrefs = []
        if kegg_genome.taxonomy_id is not None:
            taxonomy_name = pyobo.get_name('ncbitaxon', kegg_genome.taxonomy_id)
            if taxonomy_name is None:
                errors += 1
                tqdm.write(f'could not find name for taxonomy:{kegg_genome.taxonomy_id}')
            xrefs.append(Reference(
                prefix='ncbitaxon',
                identifier=kegg_genome.taxonomy_id,
                name=taxonomy_name,
            ))

        term = Term(
            reference=Reference(
                prefix='kegg.genome',
                identifier=kegg_genome.identifier,
                name=kegg_genome.name,
            ),
            xrefs=xrefs,
        )
        yield term

    logger.info('[%s] unable to find %d taxonomy names in NCBI', KEGG_GENOME_PREFIX, errors)


@click.command()
@verbose_option
def _main():
    get_obo().write_default()


if __name__ == '__main__':
    _main()
