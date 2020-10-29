# -*- coding: utf-8 -*-

"""Converter for FamPlex."""

import logging
from collections import defaultdict
from typing import Iterable

import click

from pyobo import get_name_id_mapping
from pyobo.cli_utils import verbose_option
from pyobo.path_utils import ensure_df
from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import has_member, has_part, is_a, part_of

logger = logging.getLogger(__name__)

PREFIX = 'fplx'
ENTITIES_URL = 'https://raw.githubusercontent.com/sorgerlab/famplex/master/entities.csv'
XREFS_URL = 'https://raw.githubusercontent.com/sorgerlab/famplex/master/equivalences.csv'
RELATIONS_URL = 'https://raw.githubusercontent.com/sorgerlab/famplex/master/relations.csv'


def get_obo() -> Obo:
    """Get FamPlex as OBO."""
    return Obo(
        ontology=PREFIX,
        name='FamPlex',
        iter_terms=get_terms,
        typedefs=[has_member, has_part, is_a, part_of],
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def get_terms() -> Iterable[Term]:
    """Get the FamPlex terms."""
    entities_df = ensure_df(PREFIX, ENTITIES_URL, dtype=str)
    relations_df = ensure_df(PREFIX, RELATIONS_URL, header=None, sep=',', dtype=str)

    hgnc_name_to_id = get_name_id_mapping('hgnc')
    in_edges = defaultdict(list)
    out_edges = defaultdict(list)
    for h_ns, h_name, r, t_ns, t_name in relations_df.values:
        if h_ns == 'HGNC':
            h_identifier = hgnc_name_to_id.get(h_name)
            if h_identifier is None:
                logger.warning('[%s] could not look up HGNC identifier for gene: %s', PREFIX, h_name)
            h = Reference(prefix='hgnc', identifier=h_identifier, name=h_name)
        elif h_ns == 'FPLX':
            h = Reference(prefix='fplx', identifier=h_name, name=h_name)
        elif h_ns == 'UP':
            continue
        else:
            print(h_ns)
            raise
        if t_ns == 'HGNC':
            t_identifier = hgnc_name_to_id.get(t_name)
            if t_identifier is None:
                logger.warning('[%s] could not look up HGNC identifier for gene: %s', PREFIX, t_name)
            t = Reference(prefix='hgnc', identifier=t_identifier, name=t_name)
        elif t_ns == 'FPLX':
            t = Reference(prefix='fplx', identifier=t_name, name=t_name)
        elif h_ns == 'UP':
            continue
        else:
            raise

        out_edges[h].append((r, t))
        in_edges[t].append((r, h))

    for entity, in entities_df.values:
        reference = Reference(prefix=PREFIX, identifier=entity, name=entity)
        term = Term(reference=reference)

        for r, t in out_edges.get(reference, []):
            if r == 'isa' and t.prefix == 'fplx':
                term.append_parent(t)
            elif r == 'isa':
                term.append_relationship(is_a, t)
            elif r == 'partof':
                term.append_relationship(part_of, t)
            else:
                logging.warning('unhandled relation %s', r)

        for r, h in in_edges.get(reference, []):
            if r == 'isa':
                term.append_relationship(has_member, h)
            elif r == 'partof':
                term.append_relationship(has_part, h)
            else:
                logging.warning('unhandled relation %s', r)
        yield term


@click.command()
@verbose_option
def _main():
    get_obo().write_default(use_tqdm=True)


if __name__ == '__main__':
    _main()
