# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service.

Run with ``python -m pyobo.apps.resolver``
"""

import gzip
import logging
import os
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Any, List, Mapping, Optional, Union

import click
import pandas as pd
import psutil
from flasgger import Swagger
from flask import Blueprint, Flask, current_app, jsonify, render_template
from flask_bootstrap import Bootstrap
from humanize.filesize import naturalsize
from more_click import host_option, port_option, run_app, verbose_option, with_gunicorn_option
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from tqdm import tqdm
from werkzeug.local import LocalProxy

import pyobo
from pyobo.constants import get_sqlalchemy_uri
from pyobo.identifier_utils import get_identifiers_org_link, get_obofoundry_link, get_ols_link, normalize_curie
from pyobo.resource_utils import ensure_alts, ensure_ooh_na_na

logger = logging.getLogger(__name__)

resolve_blueprint = Blueprint('resolver', __name__)


class Backend:
    """A resolution service."""

    def has_prefix(self, prefix: str) -> bool:
        """Check if there is a resource available with the given prefix."""
        raise NotImplementedError

    def get_primary_id(self, prefix: str, identifier: str) -> str:
        """Get the canonical identifier in the given resource."""
        raise NotImplementedError

    def get_name(self, prefix: str, identifier: str) -> Optional[str]:
        """Get the canonical/preferred (english) name for the identifier in the given resource."""
        raise NotImplementedError

    def get_synonyms(self, prefix: str, identifier: str) -> List[str]:
        """Get a list of synonyms."""
        raise NotImplementedError

    def get_xrefs(self, prefix: str, identifier: str) -> List[Mapping[str, str]]:
        """Get a list of xrefs."""
        raise NotImplementedError

    def summarize(self) -> Mapping[str, Any]:
        """Summarize the contents of the database."""
        raise NotImplementedError

    def count_curies(self) -> Optional[int]:
        """Count the number of identifiers in the database."""

    def count_alts(self) -> Optional[int]:
        """Count the number of alternative identifiers in the database."""

    def count_prefixes(self) -> Optional[int]:
        """Count the number of prefixes in the database."""

    def resolve(self, curie: str, resolve_alternate: bool = False) -> Mapping[str, Any]:
        """Return the results and summary when resolving a CURIE string."""
        prefix, identifier = normalize_curie(curie)
        if prefix is None:
            return dict(
                query=curie,
                success=False,
                message='Could not identify prefix',
            )

        miriam_link = get_identifiers_org_link(prefix, identifier)
        obofoundry_link = get_obofoundry_link(prefix, identifier)
        ols_link = get_ols_link(prefix, identifier)
        if not self.has_prefix(prefix):
            rv = dict(
                query=curie,
                prefix=prefix,
                identifier=identifier,
                success=False,
                message=f'Could not find id->name mapping for {prefix}',
            )
            if miriam_link:
                rv['miriam'] = miriam_link
            if obofoundry_link:
                rv['obofoundry'] = obofoundry_link
            if ols_link:
                rv['ols'] = ols_link
            return rv

        name = self.get_name(prefix, identifier)

        if name is None and resolve_alternate:
            primary_id = self.get_primary_id(prefix, identifier)
            if primary_id != identifier:
                miriam_link = get_identifiers_org_link(prefix, primary_id)
                obofoundry_link = get_obofoundry_link(prefix, primary_id)
                ols_link = get_ols_link(prefix, primary_id)
                name = self.get_name(prefix, primary_id)

        if name is None:
            return dict(
                query=curie,
                prefix=prefix,
                identifier=identifier,
                success=False,
                miriam=miriam_link,
                obofoundry=obofoundry_link,
                ols=ols_link,
                message='Could not look up identifier',
            )

        return dict(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            name=name,
            success=True,
            miriam=miriam_link,
            obofoundry=obofoundry_link,
            ols=ols_link,
        )


class MemoryBackend(Backend):
    """A resolution service using a dictionary-based in-memory cache."""

    def __init__(self, get_id_name_mapping, get_alts_to_id, summarize) -> None:  # noqa:D107
        self.get_id_name_mapping = get_id_name_mapping
        self.get_alts_to_id = get_alts_to_id
        self.summarize = summarize

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        return self.get_id_name_mapping(prefix) is not None

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        alts_to_id = self.get_alts_to_id(prefix)
        return alts_to_id.get(identifier, identifier)

    def get_name(self, prefix: str, identifier: str) -> Optional[str]:  # noqa:D102
        id_name_mapping = self.get_id_name_mapping(prefix) or {}
        return id_name_mapping.get(identifier)


class RawSQLBackend(Backend):
    """A backend that communicates with low-level SQL statements."""

    def __init__(
        self, *,
        refs_table: Optional[str] = None,
        alts_table: Optional[str] = None,
        engine=None,
    ):  # noqa:D107
        if engine is None:
            self.engine = create_engine(get_sqlalchemy_uri())
        elif isinstance(engine, str):
            self.engine = create_engine(engine)
        else:
            self.engine = engine

        self.refs_table = refs_table or 'obo_reference'
        self.alts_table = alts_table or 'obo_alt'

    @lru_cache()
    def count_curies(self) -> int:  # noqa:D102
        """Get the number of terms."""
        return self._get_one(f'SELECT COUNT(id) FROM {self.refs_table};')  # noqa:S608

    @lru_cache()
    def count_prefixes(self) -> int:  # noqa:D102
        return self._get_one(f'SELECT COUNT(DISTINCT prefix) FROM {self.refs_table};')  # noqa:S608

    @lru_cache()
    def count_alts(self) -> Optional[int]:  # noqa:D102
        return self._get_one(f'SELECT COUNT(id) FROM {self.alts_table};')  # noqa:S608

    def _get_one(self, sql: str):
        with self.engine.connect() as connection:
            result = connection.execute(sql).fetchone()
            return result[0]

    def summarize(self) -> Counter:  # noqa:D102
        sql = f'SELECT prefix, COUNT(identifier) FROM {self.refs_table} GROUP BY prefix;'  # noqa:S608
        with self.engine.connect() as connection:
            return Counter(dict(connection.execute(sql).fetchall()))

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        sql = text(f"SELECT prefix FROM {self.refs_table} WHERE prefix = :prefix LIMIT 1;")  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix).fetchone()
            return bool(result)

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        sql = text(f'''
            SELECT identifier
            FROM {self.alts_table}
            WHERE prefix = :prefix and alt = :alt LIMIT 1;
        ''')  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix, alt=identifier).fetchone()
            return result[0] if result else identifier

    def get_name(self, prefix, identifier) -> Optional[str]:  # noqa:D102
        sql = text(f"""
            SELECT name
            FROM {self.refs_table}
            WHERE prefix = :prefix and identifier = :identifier LIMIT 1;
        """)  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix, identifier=identifier).fetchone()
            if result:
                return result[0]


class SQLAlchemyBackend(Backend):
    """A resolution service using a SQL database."""

    def summarize(self) -> Mapping[str, Any]:  # noqa:D102
        from pyobo.database.sql.models import Reference
        return dict(Reference.query.groupby(Reference.prefix).count())

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        from pyobo.database.sql.models import Reference
        return Reference.query.filter(Reference.prefix == prefix).first()

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        from pyobo.database.sql.models import Alt
        new_id = Alt.query.filter(Alt.prefix == prefix, Alt.alt == identifier).one_or_none()
        if new_id is None:
            return identifier
        return new_id.identifier

    def get_name(self, prefix, identifier) -> Optional[str]:  # noqa:D102
        from pyobo.database.sql.models import Reference
        reference = Reference.query.filter(Reference.prefix == prefix, Reference.identifier == identifier).one_or_none()
        if reference:
            return reference.name

    def get_synonyms(self, prefix: str, identifier: str) -> List[str]:  # noqa:D102
        from pyobo.database.sql.models import Synonym
        synonyms = Synonym.query.filter(Synonym.prefix == prefix, Synonym.identifier == identifier).all()
        return [s.name for s in synonyms]

    def get_xrefs(self, prefix: str, identifier: str) -> List[Mapping[str, str]]:  # noqa:D102
        from pyobo.database.sql.models import Xref
        xrefs = Xref.query.filter(Xref.prefix == prefix, Xref.identifier == identifier).all()
        xrefs = {(xref.xref_prefix, xref.xref_identifier) for xref in xrefs}
        return [
            dict(prefix=xref_prefix, identifier=xref_identifier)
            for xref_prefix, xref_identifier in sorted(xrefs)
        ]


backend: Backend = LocalProxy(lambda: current_app.config['resolver_backend'])


@resolve_blueprint.route('/')
def home():
    """Serve the home page."""
    return render_template('home.html', backend=backend)


@resolve_blueprint.route('/resolve/<curie>')
def resolve(curie: str):
    """Resolve a CURIE.

    The goal of this endpoint is to resolve a CURIE.

    - ``doid:14330``, an exact match to the CURIE for Parkinson's disease in the Disease Ontology
    - ``DOID:14330``, a close match to the CURIE for Parkinson's disease in the Disease Ontology, only differing
      by capitalization
    - ``do:14330``, a match to doid via synonyms in the metaregistry. Still resolves to Parkinson's disease
      in the Disease Ontology.
    ---
    parameters:
      - name: curie
        in: path
        description: compact uniform resource identifier (CURIE) of the entity
        required: true
        type: string
        example: doid:14330
    """
    return jsonify(backend.resolve(curie))


@resolve_blueprint.route('/summary')
def summary():
    """Summary of the content in the service."""
    return jsonify(backend.summarize())


@resolve_blueprint.route('/size')
def size():
    """Return how much memory we're taking.

    Doesn't work if you're running with Gunicorn because it makes child processes.
    """
    process = psutil.Process(os.getpid())
    n_bytes = process.memory_info().rss  # in bytes
    return jsonify(
        n_bytes=n_bytes,
        n_bytes_human=naturalsize(n_bytes),
    )


def get_app(
    name_data: Union[None, str, pd.DataFrame] = None,
    alts_data: Union[None, str, pd.DataFrame] = None,
    lazy: bool = False,
    sql: bool = False,
    uri: Optional[str] = None,
    refs_table: Optional[str] = None,
    alts_table: Optional[str] = None,
) -> Flask:
    """Build a flask app.

    :param name_data: If none, uses the internal PyOBO loader. If a string, assumes is a gzip and reads a
     dataframe from there. If a dataframe, uses it directly. Assumes data frame has 3 columns - prefix,
     identifier, and name and is a TSV.
    :param alts_data: If none, uses the internal PyOBO loader. If a string, assumes is a gzip and reads a
     dataframe from there. If a dataframe, uses it directly. Assumes data frame has 3 columns - prefix,
     alt identifier, and identifier and is a TSV.
    :param lazy: don't load the full cache into memory to run
    :param sql_table: Use SQL-based backend
    """
    app = Flask(__name__)
    Swagger(app)
    Bootstrap(app)

    if sql:
        app.config['resolver_backend'] = RawSQLBackend(
            engine=uri,
            refs_table=refs_table,
            alts_table=alts_table,
        )

    else:
        if lazy:
            name_lookup = None
        elif name_data is None:
            name_lookup = _get_lookup_from_path(ensure_ooh_na_na())
        elif isinstance(name_data, str):
            name_lookup = _get_lookup_from_path(name_data)
        elif isinstance(name_data, pd.DataFrame):
            name_lookup = _get_lookup_from_df(name_data)
        else:
            raise TypeError(f'invalid type for `name_data`: {name_data}')

        if lazy:
            alts_lookup = None
        elif alts_data is None and not lazy:
            alts_lookup = _get_lookup_from_path(ensure_alts())
        elif isinstance(alts_data, str):
            alts_lookup = _get_lookup_from_path(alts_data)
        elif isinstance(alts_data, pd.DataFrame):
            alts_lookup = _get_lookup_from_df(alts_data)
        else:
            raise TypeError(f'invalid type for `alt_data`: {alts_data}')

        app.config['resolver_backend'] = _prepare_backend_with_lookup(name_lookup=name_lookup, alts_lookup=alts_lookup)

    app.register_blueprint(resolve_blueprint)
    return app


def _prepare_backend_with_lookup(
    name_lookup: Optional[Mapping[str, Mapping[str, str]]] = None,
    alts_lookup: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> Backend:
    if name_lookup is None:  # lazy mode, will download/cache data as needed
        get_id_name_mapping = pyobo.get_id_name_mapping
        summarize = Counter  # not so good to calculate this in lazy mode
    else:
        get_id_name_mapping = name_lookup.get

        def summarize():
            """Count the number of references in each resource."""
            return Counter({k: len(v) for k, v in name_lookup.items()})

    if alts_lookup is None:  # lazy mode, will download/cache data as needed
        get_alts_to_id = pyobo.get_alts_to_id
    else:
        get_alts_to_id = alts_lookup.get

    return MemoryBackend(
        get_id_name_mapping=get_id_name_mapping,
        get_alts_to_id=get_alts_to_id,
        summarize=summarize,
    )


def _get_lookup_from_df(df: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
    lookup = defaultdict(dict)
    it = tqdm(df.values, total=len(df.index), desc='loading mappings', unit_scale=True)
    for prefix, identifier, name in it:
        lookup[prefix][identifier] = name
    return dict(lookup)


def _get_lookup_from_path(path: str) -> Mapping[str, Mapping[str, str]]:
    lookup = defaultdict(dict)
    with gzip.open(path, 'rt') as path:
        _ = next(path)
        for line in tqdm(path, desc='loading mappings', unit_scale=True):
            prefix, identifier, name = line.strip().split('\t')
            lookup[prefix][identifier] = name
    return dict(lookup)


@click.command()
@click.version_option(version=pyobo.version.VERSION)
@port_option
@host_option
@click.option('--data', help='local 3-column gzipped TSV as database')
@click.option('--sql', is_flag=True)
@click.option('--sql-uri')
@click.option('--sql-refs-table', help='use preloaded SQL database as backend')
@click.option('--sql-alts-table', help='use preloaded SQL database as backend')
@click.option('--lazy', is_flag=True, help='do no load full cache into memory automatically')
@click.option('--test', is_flag=True, help='run in test mode with only a few datasets')
@click.option('--workers', type=int, help='number of workers to use in --gunicorn mode')
@with_gunicorn_option
@verbose_option
def main(
    port: str,
    host: str,
    sql: bool,
    sql_uri: str,
    sql_refs_table: str,
    sql_alts_table: str,
    data: Optional[str],
    test: bool,
    with_gunicorn: bool,
    lazy: bool,
    workers: int,
):
    """Run the resolver app."""
    if test and lazy:
        click.secho('Can not run in --test and --lazy mode at the same time', fg='red')
        sys.exit(0)

    if test:
        data = [
            (prefix, identifier, name)
            for prefix in ['hgnc', 'chebi', 'doid', 'go']
            for identifier, name in pyobo.get_id_name_mapping(prefix).items()
        ]
        data = pd.DataFrame(data, columns=['prefix', 'identifier', 'name'])

    app = get_app(
        data,
        lazy=lazy,
        sql=sql,
        uri=sql_uri,
        refs_table=sql_refs_table,
        alts_table=sql_alts_table,
    )
    run_app(app=app, host=host, port=port, with_gunicorn=with_gunicorn, workers=workers)


if __name__ == '__main__':
    main()
