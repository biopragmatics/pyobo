# -*- coding: utf-8 -*-

"""Convert KEGG Genes to OBO.

Run with ``python -m pyobo.sources.kegg.genes``
"""

import logging
from typing import Iterable, Optional

import click
from more_click import verbose_option
from tqdm import tqdm

from .api import (
    KEGGGenome, KEGG_GENES_PREFIX, ensure_conv_genome_ncbigene, ensure_conv_genome_uniprot,
    ensure_list_genome, from_kegg_species,
)
from .genome import iter_kegg_genomes
from ...io_utils import open_map_tsv
from ...struct import Obo, Reference, Term

logger = logging.getLogger(__name__)


def get_obo() -> Obo:
    """Get KEGG Genes as OBO."""
    return Obo(
        ontology=KEGG_GENES_PREFIX,
        iter_terms=iter_terms,
        typedefs=[from_kegg_species],
        name='KEGG Genes',
        auto_generated_by=f'bio2obo:{KEGG_GENES_PREFIX}',
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over terms for KEGG Genome."""
    for kegg_genome in iter_kegg_genomes():
        tqdm.write(f'Iterating {kegg_genome}')
        try:
            list_genome_path = ensure_list_genome(kegg_genome.identifier)
            conv_uniprot_path = ensure_conv_genome_uniprot(kegg_genome.identifier)
            conv_ncbigene_path = ensure_conv_genome_ncbigene(kegg_genome.identifier)
        except (OSError, ValueError) as e:
            tqdm.write(f'Failed: {e}')
        else:
            yield from _make_terms(
                kegg_genome,
                list_genome_path,
                conv_uniprot_path,
                conv_ncbigene_path,
            )


def _make_terms(
    kegg_genome: KEGGGenome,
    list_genome_path: str,
    conv_uniprot_path: Optional[str] = None,
    conv_ncbigene_path: Optional[str] = None,
) -> Iterable[Term]:
    uniprot_conv = _load_conv(conv_uniprot_path, 'up:') if conv_uniprot_path else {}
    ncbigene_conv = _load_conv(conv_ncbigene_path, 'ncbi-geneid:') if conv_ncbigene_path else {}

    with open(list_genome_path) as file:
        for line in file:
            identifier, extras = line.strip().split('\t')
            if ';' in line:
                *_extras, name = [part.strip() for part in extras.split(';')]
            else:
                name = extras

            xrefs = []

            # FIXME should these be proteins or genes?
            uniprot_xref = uniprot_conv.get(identifier)
            if uniprot_xref is not None:
                xrefs.append(Reference('uniprot', uniprot_xref))
            ncbigene_xref = ncbigene_conv.get(identifier)
            if ncbigene_xref is not None:
                xrefs.append(Reference('ncbigene', ncbigene_xref))

            term = Term(
                reference=Reference(
                    prefix=KEGG_GENES_PREFIX,
                    identifier=identifier,
                    name=name,
                ),
                xrefs=xrefs,
            )
            kegg_genome.annotate_term(term)
            yield term


def _load_conv(path, value_prefix):
    m = open_map_tsv(path)
    m = {
        k: v[len(value_prefix):]
        for k, v in m.items()
    }
    return m


@click.command()
@verbose_option
def _main():
    get_obo().write_default()


if __name__ == '__main__':
    _main()
