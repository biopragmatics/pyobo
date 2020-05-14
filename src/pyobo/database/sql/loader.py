# -*- coding: utf-8 -*-

"""A script for loading the PyOBO database."""

import logging
import time
from typing import Dict, Optional, Set, Tuple

from .backend import Reference, Resource, Synonym, Term, create_all, drop_all, session
from ... import registries
from ...extract import get_id_name_mapping, get_id_synonyms_mapping
from ...xrefdb.xrefs_pipeline import get_xref_df

__all__ = [
    'load',
]

logger = logging.getLogger(__name__)

BLACKLIST = {
    'obi',
    'ncbigene',  # too big, refs axquired from  other dbs
    'pubchem.compound',  # to big, can't deal with this now
}


def load(whitelist: Optional[Set[str]] = None) -> None:
    """Load the database.

    :param whitelist: If specified, only load ontologies with this set of prefixes
    """
    drop_all()
    create_all()

    mr = registries.get_metaregistry()

    prefix_to_resource: Dict[str, Resource] = {}
    for _, entry in sorted(mr.items()):
        if entry.prefix in BLACKLIST or (whitelist and entry.prefix not in whitelist):
            continue
        prefix_to_resource[entry.prefix] = resource = Resource(
            prefix=entry.prefix,
            name=entry.name,
            pattern=entry.pattern,
        )
        session.add(resource)

    logger.info('loading names')
    failed_prefixes = set()
    curie_to_reference: Dict[Tuple[str, str], Reference] = {}
    curie_to_term: Dict[Tuple[str, str], Term] = {}
    for prefix in mr:
        if prefix in BLACKLIST or (whitelist and prefix not in whitelist):
            continue

        try:
            id_to_name_mapping = get_id_name_mapping(prefix)
        except ValueError as e:
            failed_prefixes.add(prefix)
            logger.debug('failed for %s: %s', prefix, e)
            continue

        logger.debug('[%s] loading names', prefix)
        for identifier, name in id_to_name_mapping.items():
            curie_to_reference[prefix, identifier] = reference = Reference(
                resource=prefix_to_resource[prefix],
                identifier=identifier,
                name=name,
            )
            session.add(reference)

            curie_to_term[prefix, identifier] = term = Term(
                reference=reference,
            )
            session.add(term)

    logger.info('loading xrefs')
    unregistred_prefixes = set()
    xrefs_df = get_xref_df()
    if whitelist:
        xrefs_df = xrefs_df[xrefs_df['source_ns'].isin(whitelist)]
    for source_ns, source_id, target_ns, target_id, provenance in xrefs_df.values:
        try:
            term = curie_to_term[source_ns, source_id]
        except KeyError:
            logger.warning('could not find term for %s:%s from source %s', source_ns, source_id, provenance)
            continue

        if (target_ns, target_id) in curie_to_reference:
            xref = curie_to_reference[target_ns, target_id]
        elif target_ns in unregistred_prefixes:
            continue
        elif target_ns not in prefix_to_resource:
            logger.warning('no resource for %s. Need to update metaregistry', target_ns)
            unregistred_prefixes.add(target_ns)
            continue
        elif not target_id:
            logger.warning('got null target id in xrefs with prefix %s', target_ns)
            continue
        else:
            resource = prefix_to_resource[target_ns]
            xref = curie_to_reference[target_ns, target_id] = Reference(resource=resource, identifier=target_id)

        term.xrefs.append(xref)

    logger.info('loading synonyms')
    for prefix in mr:
        if prefix in BLACKLIST or prefix in failed_prefixes or (whitelist and prefix not in whitelist):
            continue

        try:
            id_synonyms_mapping = get_id_synonyms_mapping(prefix)
        except ValueError as e:
            logger.debug('failed for %s: %s', prefix, e)
            continue

        logger.debug('[%s] loading synonyms', prefix)
        for identifier, synonyms in id_synonyms_mapping.items():
            for synonym in synonyms:
                s = Synonym(
                    term=curie_to_term[prefix, identifier],
                    name=synonym,
                )
                session.add(s)

    t = time.time()
    logger.info('committing started at %s', time.asctime())
    try:
        session.commit()
    except Exception:
        logger.exception('commit failed at %s (%.2f seconds)', time.asctime(), time.time() - t)
    else:
        logger.info('commit ended at %s (%.2f seconds)', time.asctime(), time.time() - t)
        logger.info(f'number resources loaded: {Resource.query.count():,}')
        logger.info(f'number references loaded: {Reference.query.count():,}')
        logger.info(f'number terms loaded: {Term.query.count():,}')
        logger.info(f'number synonyms loaded: {Synonym.query.count():,}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    load()
