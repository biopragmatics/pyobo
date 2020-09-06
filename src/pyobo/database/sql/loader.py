# -*- coding: utf-8 -*-

"""A script for loading the PyOBO database."""

import gzip
import logging
from typing import Dict

import pandas as pd
from tqdm import tqdm

from .models import Alt, Reference, Resource, Synonym, Xref, create_all, drop_all, engine, session
from ... import registries
from ...resource_utils import ensure_alts, ensure_inspector_javert, ensure_ooh_na_na, ensure_synonyms

__all__ = [
    'load',
]

logger = logging.getLogger(__name__)

BLACKLIST = {
    'obi',
    'ncbigene',  # too big, refs acquired from  other dbs
    'pubchem.compound',  # to big, can't deal with this now
}


def load(
    load_resources: bool = False,
    load_names: bool = False,
    load_alts: bool = False,
    load_xrefs: bool = True,
    load_synonyms: bool = False,
    reset: bool = False,
) -> None:
    """Load the database."""
    if reset:
        drop_all()
    create_all()

    if load_resources:
        metaregistry = registries.get_metaregistry()
        prefix_to_resource: Dict[str, Resource] = {}
        for resource_dataclass in tqdm(metaregistry.values(), desc='loading resources'):
            prefix_to_resource[resource_dataclass.prefix] = resource_model = Resource(
                prefix=resource_dataclass.prefix,
                name=resource_dataclass.name,
                pattern=resource_dataclass.pattern,
            )
            session.add(resource_model)
        session.commit()

    ooh_na_na_path = ensure_ooh_na_na()
    synonyms_path = ensure_synonyms()
    xrefs_path = ensure_inspector_javert()

    if load_alts:
        alts_path = ensure_alts()
        alts_df = pd.read_csv(alts_path, sep='\t', dtype=str)  # prefix, alt, identifier
        logger.info('inserting %d alt identifiers', len(alts_df.index))
        alts_df.to_sql(name=Alt.__tablename__, con=engine, if_exists='append', index=False)
        logger.info('committing alt identifier')
        session.commit()
        logger.info('done committing alt identifiers')

    for label, path, table, checker in [
        ('names', ooh_na_na_path, Reference, load_names),
        ('synonyms', synonyms_path, Synonym, load_synonyms),
        ('xrefs', xrefs_path, Xref, load_xrefs),
    ]:
        if not checker:
            continue
        logger.info('beginning insertion of %', label)
        conn = engine.raw_connection()
        logger.info('inserting with low-level copy of % from: %s', label, path)
        with conn.cursor() as cursor, gzip.open(path) as file:
            next(file)  # skip the header
            cursor.copy_from(file, table.__tablename__, sep='\t')  # insert the table
        logger.info('committing %s', label)
        conn.commit()
        logger.info('done committing %s', label)

    logger.info(f'number resources loaded: {Resource.query.count():,}')
    logger.info(f'number references loaded: {Reference.query.count():,}')
    logger.info(f'number alts loaded: {Alt.query.count():,}')
    logger.info(f'number synonyms loaded: {Synonym.query.count():,}')
    logger.info(f'number xrefs loaded: {Xref.query.count():,}')

    return

    # if load_xrefs:
    #     unregistered_prefixes = set()
    #     xrefs_df = get_xref_df(use_cached=use_cached)
    #     if whitelist:
    #         logger.info('slicing xrefs to whitelist: %s', whitelist)
    #         xrefs_df = xrefs_df[xrefs_df['source_ns'].isin(whitelist)]
    #
    #     it = tqdm(xrefs_df.values, desc='loading xrefs', unit_scale=True)
    #     for source_ns, source_id, target_ns, target_id, provenance in it:
    #         try:
    #             term = curie_to_term[source_ns, source_id]
    #         except KeyError:
    #             logger.warning('could not find term for %s:%s from source %s', source_ns, source_id, provenance)
    #             continue
    #
    #         if (target_ns, target_id) in curie_to_reference:
    #             xref = curie_to_reference[target_ns, target_id]
    #         elif target_ns in unregistered_prefixes:
    #             continue
    #         elif target_ns not in prefix_to_resource:
    #             logger.warning('no resource for %s. Need to update metaregistry', target_ns)
    #             unregistered_prefixes.add(target_ns)
    #             continue
    #         elif not target_id:
    #             logger.warning('got null target id in xrefs with prefix %s', target_ns)
    #             continue
    #         else:
    #             resource_model = prefix_to_resource[target_ns]
    #             xref = curie_to_reference[target_ns, target_id] = Reference(resource=resource_model,
    #                                                                         identifier=target_id)
    #
    #         term.xrefs.append(xref)
    #
    # if load_synonyms:
    #     for resource_dataclass in tqdm(resources_dataclasses, desc='loading synonyms'):
    #         prefix = resource_dataclass.prefix
    #         try:
    #             id_synonyms_mapping = get_id_synonyms_mapping(prefix)
    #         except ValueError as e:
    #             logger.debug('failed for %s: %s', prefix, e)
    #             continue
    #
    #         for identifier, synonyms in tqdm(
    #             id_synonyms_mapping.items(), leave=False, unit_scale=True, desc=f'[{prefix}] loading synonyms',
    #         ):
    #             for synonym in synonyms:
    #                 term = curie_to_term.get((prefix, identifier))
    #                 if term is None:
    #                     logger.warning('[%s] missing identifier %s', prefix, identifier)
    #                     continue
    #                 s = Synonym(
    #                     term=term,
    #                     name=synonym,
    #                 )
    #                 session.add(s)
    #
    # t = time.time()
    # logger.info('committing started at %s', time.asctime())
    # try:
    #     session.commit()
    # except Exception:
    #     logger.exception('commit failed at %s (%.2f seconds)', time.asctime(), time.time() - t)
    # else:
    #     logger.info('commit ended at %s (%.2f seconds)', time.asctime(), time.time() - t)
    #     logger.info(f'number resources loaded: {Resource.query.count():,}')
    #     logger.info(f'number references loaded: {Reference.query.count():,}')
    #     logger.info(f'number terms loaded: {Term.query.count():,}')
    #     logger.info(f'number synonyms loaded: {Synonym.query.count():,}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    load()
