# -*- coding: utf-8 -*-

"""Utilities for extracting synonyms."""

import logging
import os
from collections import defaultdict
from typing import List, Mapping, Optional

from pyobo.utils import get_obo_graph, get_prefix_directory, split_tab_pair

logger = logging.getLogger(__name__)


def get_synonyms(prefix: str, url: Optional[str] = None) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = os.path.join(get_prefix_directory(prefix), f"{prefix}_synonyms.tsv")

    rv = defaultdict(list)
    if os.path.exists(path):
        logger.debug('loading %s synonyms from %s', prefix, path)
        with open(path) as file:
            next(file)  # throw away header
            for line in file:
                x, y = split_tab_pair(line)
                rv[x].append(y)
            return dict(rv)

    graph = get_obo_graph(prefix, url=url)

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

    with open(path, 'w') as file:
        print(f'{prefix}_id', f'synonym', sep='\t', file=file)  # add header
        for identifier, synonyms in rv.items():
            for synonym in synonyms:
                print(identifier, synonym, sep='\t', file=file)

    return dict(rv)
