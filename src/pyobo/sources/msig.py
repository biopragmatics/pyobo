# -*- coding: utf-8 -*-

"""Parsers for MSig."""

import logging
import os
from functools import partial
from typing import Iterable

import scrapy
from scrapy.crawler import CrawlerProcess

from .gmt_utils import parse_gmt_file
from ..path_utils import prefix_directory_join
from ..struct import Obo, Reference, Term
from ..struct.defs import pathway_has_part

logger = logging.getLogger(__name__)

PREFIX = 'msig'
VERSION = '7.0'

BASE_URL = 'http://software.broadinstitute.org/gsea/msigdb/download_file.jsp?filePath=/resources/msigdb'
GMT_ENTREZ_URL = f'{BASE_URL}/{VERSION}/msigdb.v{VERSION}.entrez.gmt'
GMT_HGNC_URL = f'{BASE_URL}/{VERSION}/msigdb.v{VERSION}.symbols.gmt'

GMT_ENTREZ_PATH = prefix_directory_join(PREFIX, f'msigdb.v{VERSION}.entrez.gmt', version=VERSION)
GMT_HGNC_PATH = prefix_directory_join(PREFIX, f'msigdb.v{VERSION}.symbols.gmt', version=VERSION)


class GSEASpider(scrapy.Spider):
    """A Scrapy Spider for downloading GMT files from GSEA."""

    name = 'bio2bel'
    start_urls = ['http://software.broadinstitute.org/gsea/login.jsp']

    def parse(self, response):
        """Fill out the GSEA login form."""
        return scrapy.FormRequest.from_response(
            response,
            formdata={
                'j_username': 'cthoyt@gmail.com',
                'j_password': 'password',
            },
            callback=self.after_login,
        )

    def after_login(self, _):
        """Redirect to the Downloads page."""
        yield scrapy.Request('http://software.broadinstitute.org/gsea/downloads.jsp', callback=self.download_file)

    def download_file(self, _):
        """Redirect to the file path and download with a callback."""
        yield scrapy.Request(GMT_ENTREZ_URL, callback=partial(self.save_gmt, path=GMT_ENTREZ_PATH))
        yield scrapy.Request(GMT_HGNC_URL, callback=partial(self.save_gmt, path=GMT_HGNC_PATH))

    @staticmethod
    def save_gmt(response, *, path):
        """Save the GMT file."""
        with open(path, 'wb') as f:
            f.write(response.body)


def ensure_msig_path() -> str:
    """Download the GSEA data and return the path."""
    if not os.path.exists(GMT_ENTREZ_PATH):
        process = CrawlerProcess({
            'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
        })
        process.crawl(GSEASpider)
        process.start()
        process.join()
    return GMT_ENTREZ_PATH


def get_obo() -> Obo:
    """Get MSIG as Obo."""
    return Obo(
        ontology=PREFIX,
        name='Molecular Signatures Database',
        iter_terms=iter_terms,
    )


def iter_terms() -> Iterable[Term]:
    """Get MSIG terms."""
    path = ensure_msig_path()
    for identifier, name, genes in parse_gmt_file(path):
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )
        for ncbigene_id in genes:
            term.append_relationship(pathway_has_part, Reference(prefix='ncbigene', identifier=ncbigene_id))
        yield term
