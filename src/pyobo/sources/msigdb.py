# -*- coding: utf-8 -*-

"""Parsers for MSig."""

import logging
from typing import Iterable

import bioversions
import click
from more_click import verbose_option

from .gmt_utils import parse_gmt_file
from ..path_utils import ensure_path
from ..struct import Obo, Reference, Term
from ..struct.typedef import has_part

logger = logging.getLogger(__name__)

PREFIX = 'msigdb'
BASE_URL = 'https://data.broadinstitute.org/gsea-msigdb/msigdb/release'


def ensure_msigdb_path(version: str):
    """Download the GSEA data and return the path."""
    xml_url = f'{BASE_URL}/{version}/msigdb.v{version}.xml'
    entrez_url = f'{BASE_URL}/{version}/msigdb.v{version}.entrez.gmt'
    hgnc_url = f'{BASE_URL}/{version}/msigdb.v{version}.symbols.gmt'
    xml_path = ensure_path(prefix=PREFIX, url=xml_url, version=version)
    entrez_path = ensure_path(prefix=PREFIX, url=entrez_url, version=version)
    hgnc_path = ensure_path(prefix=PREFIX, url=hgnc_url, version=version)
    return xml_path, entrez_path, hgnc_path


def get_obo() -> Obo:
    """Get MSIG as Obo."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name='Molecular Signatures Database',
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        data_version=version,
        auto_generated_by=f'bio2obo:{PREFIX}',
        typedefs=[has_part],
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Get MSigDb terms."""
    _, path, _ = ensure_msigdb_path(version)
    for identifier, name, genes in parse_gmt_file(path):
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )
        for ncbigene_id in genes:
            term.append_relationship(has_part, Reference(prefix='ncbigene', identifier=ncbigene_id))
        yield term


@click.command()
@verbose_option
def _main():
    get_obo().write_default()


if __name__ == '__main__':
    _main()
