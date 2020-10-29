# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import gzip
import logging
import os
from collections import Counter
from typing import Callable, Iterable, Mapping, Optional, Tuple, TypeVar
from urllib.request import urlretrieve

import obonet
from tqdm import tqdm

from .constants import DATABASE_DIRECTORY
from .identifier_utils import get_metaregistry, wrap_norm_prefix
from .path_utils import ensure_path, get_prefix_directory, get_prefix_obo_path
from .registries import get_curated_urls, get_obofoundry
from .sources import has_nomenclature_plugin, run_nomenclature_plugin
from .struct import Obo

__all__ = [
    'get',
    'MissingOboBuild',
    'NoOboFoundry',
]

logger = logging.getLogger(__name__)


class MissingOboBuild(RuntimeError):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


class NoOboFoundry(ValueError):
    """Raised when OBO foundry doesn't have it."""


@wrap_norm_prefix
def get(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO for a given graph.

    :param prefix: The prefix of the ontology to look up
    :param url: A URL to give if the OBOfoundry can not be used to look up the given prefix
    :param local: A local file path is given. Do not cache.
    """
    path = os.path.join(get_prefix_directory(prefix), f'{prefix}.obonet.json.gz')
    if os.path.exists(path) and not local:
        logger.debug('[%s] using obonet cache at %s', prefix, path)
        return Obo.from_obonet_gz(path)
    else:
        logger.debug('[%s] no obonet cache found at %s', prefix, path)

    if has_nomenclature_plugin(prefix):
        obo = run_nomenclature_plugin(prefix)
        logger.info('[%s] caching OBO at %s', prefix, path)
        obo.write_default()
    else:
        obo = _get_obo_via_obonet(prefix=prefix, url=url, local=local)

    if not local:
        logger.info('[%s] caching pre-compiled OBO at %s', prefix, path)
        obo.write_obonet_gz(path)

    return obo


def _get_obo_via_obonet(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO file by prefix or URL."""
    if url is None:
        path = _ensure_obo_path(prefix)
    elif local:
        path = url
    else:
        path = get_prefix_obo_path(prefix)
        if not os.path.exists(path):
            logger.info('[%s] downloading OBO from %s to %s', prefix, url, path)
            urlretrieve(url, path)

    logger.info('[%s] parsing with obonet from %s', prefix, path)
    with open(path) as file:
        graph = obonet.read_obo(tqdm(file, unit_scale=True, desc=f'[{prefix}] parsing obo'))
    if 'ontology' not in graph.graph:
        logger.warning('[%s] missing "ontology" key', prefix)
        graph.graph['ontology'] = prefix
    elif not graph.graph['ontology'].isalpha():
        logger.warning('[%s] ontology=%s has a strange format. replacing with prefix', prefix, graph.graph['ontology'])
        graph.graph['ontology'] = prefix
    return Obo.from_obonet(graph)


def _ensure_obo_path(prefix: str) -> str:
    """Get the path to the OBO file and download if missing."""
    curated_url = get_curated_urls().get(prefix)
    if curated_url:
        logger.debug('[%s] checking for OBO at curated URL: %s', prefix, curated_url)
        return ensure_path(prefix, url=curated_url)

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        logger.debug('[%s] OBO already exists at %s', prefix, path)
        return path

    obofoundry = get_obofoundry(mappify=True)
    entry = obofoundry.get(prefix)
    if entry is None:
        raise NoOboFoundry(f'OBO Foundry is missing the prefix: {prefix}')

    build = entry.get('build')
    if build is None:
        raise MissingOboBuild(f'OBO Foundry is missing a build for: {prefix}')

    url = build.get('source_url')
    if url is None:
        raise MissingOboBuild(f'OBO Foundry build is missing a URL for: {prefix}, {build}')

    return ensure_path(prefix, url)


SKIP = {
    'obi',
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
    'rnao',  # just really malformed, way too much unconverted OWL
    'gaz',
    'mamo',
    'ido',
    'iao',
    'geo',
}

X = TypeVar('X')


def iter_helper(f: Callable[[str], Mapping[str, X]], leave: bool = False) -> Iterable[Tuple[str, str, X]]:
    """Yield all mappings extracted from each database given."""
    for prefix in sorted(get_metaregistry()):
        if prefix in SKIP:
            continue
        try:
            mapping = f(prefix)
        except (NoOboFoundry, MissingOboBuild):
            continue
        except ValueError as e:
            if (
                str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0"?>')
                or str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>')
            ):
                logger.info('no resource available for %s. See http://www.obofoundry.org/ontology/%s', prefix, prefix)
                continue  # this means that it tried doing parsing on an xml page saying get the fuck out
            logger.warning('could not successfully parse %s: %s', prefix, e)
        else:
            for key, value in tqdm(mapping.items(), desc=f'iterating {prefix}', leave=leave, unit_scale=True):
                yield prefix, key, value


def db_output_helper(directory, f, db_name, columns) -> None:
    """Help output database builds."""
    c = Counter()
    db_path = os.path.join(DATABASE_DIRECTORY, f'{db_name}.tsv.gz')
    db_sample_path = os.path.join(DATABASE_DIRECTORY, f'{db_name}_sample.tsv')
    logger.info('Writing %s to %s', db_name, db_path)

    it = f()
    with gzip.open(db_path, mode='wt') as gzipped_file:
        # for the first 10 rows, put it in a sample file too
        with open(db_sample_path, 'w') as sample_file:
            print(*columns, sep='\t', file=gzipped_file)
            print(*columns, sep='\t', file=sample_file)

            for _ in range(10):
                prefix, identifier, name = next(it)
                c[prefix] += 1
                print(prefix, identifier, name, sep='\t', file=gzipped_file)
                print(prefix, identifier, name, sep='\t', file=sample_file)

        # continue just in the gzipped one
        for prefix, identifier, name in it:
            c[prefix] += 1
            print(prefix, identifier, name, sep='\t', file=gzipped_file)

    summary_path = os.path.join(directory, f'{db_name}_summary.tsv')
    logger.info(f'Writing {db_name} summary to {summary_path}')
    with open(summary_path, 'w') as file:
        for k, v in c.most_common():
            print(k, v, sep='\t', file=file)
