# -*- coding: utf-8 -*-

"""Convert KEGG Genes to OBO.

Run with ``python -m pyobo.sources.kegg.genes``
"""

import logging
from typing import Iterable

import click
from more_click import verbose_option

from pyobo.sources.kegg.api import (
    KEGG_GENES_PREFIX, ensure_conv_genome_ncbigene, ensure_conv_genome_uniprot,
    ensure_list_genome,
)
from pyobo.sources.kegg.genome import iter_kegg_genomes
from pyobo.struct import Obo, Term

logger = logging.getLogger(__name__)


def get_obo() -> Obo:
    """Get KEGG Genes as OBO."""
    return Obo(
        ontology=KEGG_GENES_PREFIX,
        iter_terms=iter_terms,
        name='KEGG Genes',
        auto_generated_by=f'bio2obo:{KEGG_GENES_PREFIX}',
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over terms for KEGG Genome."""
    for kegg_genome in iter_kegg_genomes():
        try:
            list_genome_path = ensure_list_genome(kegg_genome.identifier)
            conv_uniprot_path = ensure_conv_genome_uniprot(kegg_genome.identifier)
            conv_ncbigene_path = ensure_conv_genome_ncbigene(kegg_genome.identifier)
        except (OSError, ValueError):
            pass
        else:
            _make_term(list_genome_path, conv_uniprot_path, conv_ncbigene_path)


def _make_term(list_genome_path, conv_uniprot_path, conv_ncbigene_path):
    pass


@click.command()
@verbose_option
def _main():
    iter_terms()


if __name__ == '__main__':
    _main()
