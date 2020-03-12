# -*- coding: utf-8 -*-

"""Utilities for extracting synonyms."""

import logging
import os
from collections import defaultdict
from typing import List, Mapping, Optional

from ..getters import get_obo_graph
from ..io_utils import open_multimap_tsv, write_multimap_tsv
from ..path_utils import prefix_directory_join

__all__ = [
    'get_synonyms',
]

logger = logging.getLogger(__name__)


def get_synonyms(prefix: str, url: Optional[str] = None) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, f"{prefix}_synonyms.tsv")
    if os.path.exists(path):
        logger.debug('loading %s synonyms from %s', prefix, path)
        return open_multimap_tsv(path)

    graph = get_obo_graph(prefix, url=url)

    rv = defaultdict(list)
    for node, data in graph.nodes(data=True):
        if not node.lower().startswith(f'{prefix.lower()}:'):
            continue

        name = data['name']
        rv[node].append(name)

        for synonym in data.get('synonym', []):
            synonym = synonym.strip('"')
            if not synonym:
                continue

            if "RELATED" in synonym:
                synonym = synonym[:synonym.index('RELATED')].rstrip().rstrip('"')
            elif "EXACT" in synonym:
                synonym = synonym[:synonym.index('EXACT')].rstrip().rstrip('"')
            elif "BROAD" in synonym:
                synonym = synonym[:synonym.index('BROAD')].rstrip().rstrip('"')
            else:
                logger.warning(f'For {node} unhandled synonym: {synonym}')
                continue

            rv[node].append(synonym)

    rv = {
        k: sorted(set(v))
        for k, v in rv.items()
    }

    write_multimap_tsv(path=path, header=[f'{prefix}_id', f'synonym'], rv=rv)

    return rv
