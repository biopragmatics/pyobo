# -*- coding: utf-8 -*-

"""A script for loading the PyOBO database."""

import gzip
import logging
from typing import Dict

import bioregistry
import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

from .models import Alt, Reference, Resource, Synonym, Xref, create_all, drop_all, engine, session
from ...resource_utils import (
    ensure_alts,
    ensure_inspector_javert,
    ensure_ooh_na_na,
    ensure_synonyms,
)

__all__ = [
    "load",
]

logger = logging.getLogger(__name__)


@click.command()
@verbose_option
@click.option("--load-resources", is_flag=True)
@click.option("--load-names", is_flag=True)
@click.option("--load-alts", is_flag=True)
@click.option("--load-xrefs", is_flag=True)
@click.option("--load-synonyms", is_flag=True)
@click.option("-a", "--load-all", is_flag=True)
@click.option("--reset", is_flag=True)
def load(
    load_all: bool,
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

    if load_resources or load_all:
        prefix_to_resource: Dict[str, Resource] = {}
        prefixes = {resource.prefix for resource in Resource.query.all()}

        for prefix, entry in tqdm(bioregistry.read_registry().items(), desc="loading resources"):
            if bioregistry.is_deprecated(prefix):
                continue
            if prefix in prefixes:
                continue
            prefix_to_resource[prefix] = resource_model = Resource(
                prefix=prefix,
                name=entry["name"],
                pattern=bioregistry.get_pattern(prefix),
            )
            session.add(resource_model)
        session.commit()

    ooh_na_na_path = ensure_ooh_na_na()
    synonyms_path = ensure_synonyms()
    xrefs_path = ensure_inspector_javert()

    if load_alts or load_all:
        alts_path = ensure_alts()
        alts_df = pd.read_csv(alts_path, sep="\t", dtype=str)  # prefix, alt, identifier
        logger.info("inserting %d alt identifiers", len(alts_df.index))
        alts_df.to_sql(name=Alt.__tablename__, con=engine, if_exists="append", index=False)
        logger.info("committing alt identifier")
        session.commit()
        logger.info("done committing alt identifiers")

    for label, path, table, columns, checker in [
        ("names", ooh_na_na_path, Reference, None, load_names),
        ("synonyms", synonyms_path, Synonym, ["prefix", "identifier", "name"], load_synonyms),
        (
            "xrefs",
            xrefs_path,
            Xref,
            ["prefix", "identifier", "xref_prefix", "xref_identifier", "source"],
            load_xrefs,
        ),
    ]:
        if not checker and not load_all:
            continue
        logger.info("beginning insertion of %s", label)
        conn = engine.raw_connection()
        logger.info("inserting with low-level copy of %s from: %s", label, path)
        if columns:
            columns = ", ".join(columns)
            logger.info("corresponding to columns: %s", columns)
            columns = f" ({columns})"
        else:
            columns = ""

        with conn.cursor() as cursor, gzip.open(path) as file:
            # next(file)  # skip the header
            sql = f"""COPY {table.__tablename__}{columns} FROM STDIN WITH CSV HEADER DELIMITER E'\\t' QUOTE E'\\b';"""
            logger.info("running SQL: %s", sql)
            cursor.copy_expert(sql=sql, file=file)

        logger.info("committing %s", label)
        conn.commit()
        logger.info("done committing %s", label)

    logger.info(f"number resources loaded: {Resource.query.count():,}")
    logger.info(f"number references loaded: {Reference.query.count():,}")
    logger.info(f"number alts loaded: {Alt.query.count():,}")
    logger.info(f"number synonyms loaded: {Synonym.query.count():,}")
    logger.info(f"number xrefs loaded: {Xref.query.count():,}")


if __name__ == "__main__":
    load()
