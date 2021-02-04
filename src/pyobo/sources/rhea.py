# -*- coding: utf-8 -*-

"""Converter for Rhea."""

import logging
from typing import Iterable

import bioversions
from pyobo.path_utils import ensure_df
from pyobo.struct import Obo, Reference, Term, TypeDef

logger = logging.getLogger(__name__)
PREFIX = 'rhea'
RHEA_DATA = 'ftp://ftp.expasy.org/databases/rhea/tsv/rhea-tsv.tar.gz'

has_lr = TypeDef(Reference(PREFIX, 'has_lr_reaction'))
has_rl = TypeDef(Reference(PREFIX, 'has_rl_reaction'))
has_bi = TypeDef(Reference(PREFIX, 'has_bi_reaction'))


def get_obo() -> Obo:
    """Get Rhea as OBO."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name='Rhea',
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        data_version=version,
        auto_generated_by=f'bio2obo:{PREFIX}',
        typedefs=[has_lr, has_bi, has_rl],
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over terms in Rhea."""
    terms = {}

    directions = ensure_df(PREFIX, url='ftp://ftp.expasy.org/databases/rhea/tsv/rhea-directions.tsv', version=version)
    for master, lr, rl, bi in directions.values:
        terms[master] = Term(reference=Reference(PREFIX, master))
        terms[lr] = Term(reference=Reference(PREFIX, lr))
        terms[rl] = Term(reference=Reference(PREFIX, rl))
        terms[bi] = Term(reference=Reference(PREFIX, bi))

        terms[master].append_relationship(has_lr, terms[lr])
        terms[master].append_relationship(has_rl, terms[rl])
        terms[master].append_relationship(has_bi, terms[bi])
        terms[lr].append_parent(terms[master])
        terms[rl].append_parent(terms[master])
        terms[bi].append_parent(terms[master])

    hierarchy = ensure_df(PREFIX, url='ftp://ftp.expasy.org/databases/rhea/tsv/rhea-relationships.tsv', version=version)
    for source, relation, target in hierarchy.values:
        if relation != 'is_a':
            raise ValueError(f'RHEA unrecognized relation: {relation}')
        terms[source].append_parent(terms[target])

    ecocyc = ensure_df(PREFIX, url='ftp://ftp.expasy.org/databases/rhea/tsv/rhea2ecocyc.tsv', version=version)
    for rhea_id, _, _, ecocyc_id in ecocyc.values:
        terms[rhea_id].append_xref(Reference('ecocyc', ecocyc_id))

    kegg = ensure_df(PREFIX, url='ftp://ftp.expasy.org/databases/rhea/tsv/rhea2kegg_reaction.tsv', version=version)
    for rhea_id, _, _, kegg_id in kegg.values:
        if rhea_id not in terms:
            logger.warning('missing rhea:%s', rhea_id)
            continue
        terms[rhea_id].append_xref(Reference('kegg.pathway', kegg_id))

    reactome = ensure_df(PREFIX, url='ftp://ftp.expasy.org/databases/rhea/tsv/rhea2reactome.tsv', version=version)
    for rhea_id, _, _, reactome_id in reactome.values:
        terms[rhea_id].append_xref(Reference('reactome', reactome_id))

    # TODO names?

    yield from terms.values()


if __name__ == '__main__':
    get_obo().write_default(force=True, write_obo=True)
