# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import datetime
import gzip
import json
import logging
import os
import urllib.error
import zipfile
from collections import Counter
from typing import Callable, Iterable, Mapping, Optional, Tuple, TypeVar
from urllib.request import urlretrieve

import bioregistry
import obonet
from bioregistry.external import get_obofoundry
from tqdm import tqdm

from .constants import DATABASE_DIRECTORY
from .identifier_utils import wrap_norm_prefix
from .path_utils import ensure_path, get_prefix_obo_path, prefix_directory_join
from .registries import get_curated_urls
from .sources import has_nomenclature_plugin, run_nomenclature_plugin
from .struct import Obo
from .version import get_git_hash, get_version

__all__ = [
    'get',
    'MissingOboBuild',
    'NoOboFoundry',
]

logger = logging.getLogger(__name__)


class NoBuild(RuntimeError):
    """Base exception for being unable to build."""


class MissingOboBuild(NoBuild):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


class NoOboFoundry(NoBuild):
    """Raised when OBO foundry doesn't have it."""


class OnlyOWLError(NoBuild):
    """Only OWL is available."""


@wrap_norm_prefix
def get(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO for a given graph.

    :param prefix: The prefix of the ontology to look up
    :param url: A URL to give if the OBOfoundry can not be used to look up the given prefix
    :param local: A local file path is given. Do not cache.
    """
    path = prefix_directory_join(prefix, f'{prefix}.obonet.json.gz')
    if path.exists() and not local:
        logger.debug('[%s] using obonet cache at %s', prefix, path)
        return Obo.from_obonet_gz(path)
    elif has_nomenclature_plugin(prefix):
        obo = run_nomenclature_plugin(prefix)
        logger.info('[%s] caching nomenclature plugin', prefix)
        obo.write_default()
        return obo
    else:
        logger.debug('[%s] no obonet cache found at %s', prefix, path)

    obo = _get_obo_via_obonet(prefix=prefix, url=url, local=local)
    if not local:
        obo.write_default()

    return obo


def _get_obo_via_obonet(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO file by prefix or URL."""
    path = _get_path(prefix=prefix, url=url, local=local)
    if path.endswith('.owl'):
        raise OnlyOWLError(f'[{prefix}] unhandled OWL file')

    logger.info('[%s] parsing with obonet from %s', prefix, path)
    with open(path) as file:
        graph = obonet.read_obo(tqdm(file, unit_scale=True, desc=f'[{prefix}] parsing obo'))

    # Make sure the graph is named properly
    _clean_graph_ontology(graph, prefix)

    # Convert to an Obo instance and return
    return Obo.from_obonet(graph)


def _get_path(*, url, prefix, local) -> str:
    if url is None:
        path = _ensure_obo_path(prefix)
    elif local:
        path = url
    else:
        path = get_prefix_obo_path(prefix)
        if path.exists():
            logger.info('[%s] downloading OBO from %s to %s', prefix, url, path)
            urlretrieve(url, path)
    return path


def _clean_graph_ontology(graph, prefix: str) -> None:
    """Update the ontology entry in the graph's metadata, if necessary."""
    if 'ontology' not in graph.graph:
        logger.warning('[%s] missing "ontology" key', prefix)
        graph.graph['ontology'] = prefix
    elif not graph.graph['ontology'].isalpha():
        logger.warning('[%s] ontology=%s has a strange format. replacing with prefix', prefix, graph.graph['ontology'])
        graph.graph['ontology'] = prefix


def _ensure_obo_path(prefix: str) -> str:
    """Get the path to the OBO file and download if missing."""
    curated_url = get_curated_urls().get(prefix)
    if curated_url:
        logger.debug('[%s] checking for OBO at curated URL: %s', prefix, curated_url)
        return ensure_path(prefix, url=curated_url)

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        logger.debug('[%s] OBO already exists at %s', prefix, path)
        return path.as_posix()

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

    return ensure_path(prefix, url=url)


SKIP = {
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
    'gaz',  # Gazetteer is irrelevant for biology
    'ma',  # yanked
    # FIXME below
    'mirbase.family',
    'pfam.clan',
}

X = TypeVar('X')


def iter_helper(f: Callable[[str], Mapping[str, X]], leave: bool = False) -> Iterable[Tuple[str, str, X]]:
    """Yield all mappings extracted from each database given."""
    for prefix, mapping in iter_helper_helper(f):
        for key, value in tqdm(mapping.items(), desc=f'iterating {prefix}', leave=leave, unit_scale=True):
            yield prefix, key, value


def iter_helper_helper(f: Callable[[str], X], strict: bool = True) -> Iterable[Tuple[str, X]]:
    """Yield all mappings extracted from each database given.

    :param f: A function that takes a prefix and gives back something that will be used by an outer function.
    :param strict: If true, will raise exceptions and crash the program instead of logging them.
    :raises HTTPError: If the resource could not be downloaded
    :raises URLError: If another problem was encountered during download
    :raises ValueError: If the data was not in the format that was expected (e.g., OWL)
    """
    it = tqdm(sorted(bioregistry.read_bioregistry()))
    for prefix in it:
        if prefix in SKIP:
            continue
        it.set_postfix({'prefix': prefix})
        try:
            mapping = f(prefix)
        except NoBuild:
            continue
        except urllib.error.HTTPError as e:
            logger.warning('[%s] HTTP %s: unable to download %s', prefix, e.getcode(), e.geturl())
            if strict:
                raise
        except urllib.error.URLError:
            logger.warning('[%s] unable to download', prefix)
            if strict:
                raise
        except zipfile.BadZipFile as e:
            logger.warning('[%s] bad zip file: %s', prefix, e)
        except ValueError as e:
            if _is_xml(e):
                # this means that it tried doing parsing on an xml page saying get the fuck out
                logger.info('no resource available for %s. See http://www.obofoundry.org/ontology/%s', prefix, prefix)
            else:
                logger.warning('[%s] error while parsing: %s', prefix, e)
            if strict:
                raise e
        else:
            yield prefix, mapping


def _is_xml(e) -> bool:
    return (
        str(e).startswith('Tag-value pair parsing failed for:')
        or str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>')
    )


def db_output_helper(f, db_name, columns) -> None:
    """Help output database builds."""
    c = Counter()

    db_metadata_path = DATABASE_DIRECTORY / f'{db_name}_metadata.json'
    with open(db_metadata_path, 'w') as file:
        json.dump(
            {
                'version': get_version(),
                'git_hash': get_git_hash(),
                'date': datetime.datetime.now().strftime('%Y-%m-%d-%H-%M'),
            },
            file,
            indent=2,
        )

    db_path = DATABASE_DIRECTORY / f'{db_name}.tsv.gz'
    db_sample_path = DATABASE_DIRECTORY / f'{db_name}_sample.tsv'
    db_summary_path = DATABASE_DIRECTORY / f'{db_name}_summary.tsv'

    logger.info('writing %s to %s', db_name, db_path)
    logger.info('writing %s sample to %s', db_name, db_sample_path)
    it = f()
    with gzip.open(db_path, mode='wt') as gzipped_file:
        # for the first 10 rows, put it in a sample file too
        with open(db_sample_path, 'w') as sample_file:
            print(*columns, sep='\t', file=gzipped_file)
            print(*columns, sep='\t', file=sample_file)

            for (prefix, identifier, name), _ in zip(it, range(10)):
                c[prefix] += 1
                print(prefix, identifier, name, sep='\t', file=gzipped_file)
                print(prefix, identifier, name, sep='\t', file=sample_file)

        # continue just in the gzipped one
        for prefix, identifier, name in it:
            c[prefix] += 1
            print(prefix, identifier, name, sep='\t', file=gzipped_file)

    logger.info(f'writing {db_name} summary to {db_summary_path}')
    with open(db_summary_path, 'w') as file:
        for k, v in c.most_common():
            print(k, v, sep='\t', file=file)
