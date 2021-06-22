# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service.

Run with ``python -m pyobo.apps.resolver``
"""

import gzip
import logging
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Optional, Union

import pandas as pd
from flasgger import Swagger
from flask import Blueprint, Flask, current_app, jsonify, render_template
from flask_bootstrap import Bootstrap
from humanize import intcomma
from humanize.filesize import naturalsize
from tqdm import tqdm
from werkzeug.local import LocalProxy

import pyobo
from pyobo.apps.resolver.backends import Backend, MemoryBackend, RawSQLBackend
from pyobo.resource_utils import ensure_alts, ensure_definitions, ensure_ooh_na_na

logger = logging.getLogger(__name__)

resolve_blueprint = Blueprint("resolver", __name__)

backend: Backend = LocalProxy(lambda: current_app.config["resolver_backend"])


@resolve_blueprint.route("/")
def home():
    """Serve the home page."""
    return render_template(
        "home.html",
        name_count=intcomma(backend.count_names()),
        alts_count=intcomma(backend.count_alts()),
        prefix_count=intcomma(backend.count_prefixes()),
        definition_count=intcomma(backend.count_definitions()),
    )


@resolve_blueprint.route("/resolve/<curie>")
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


@resolve_blueprint.route("/summary")
def summary():
    """Serve the summary page."""
    return render_template(
        "summary.html",
        summary_df=backend.summary_df(),
    )


@resolve_blueprint.route("/summary.json")
def summary_json():
    """Summary of the content in the service."""
    return jsonify(backend.summarize_names())


@resolve_blueprint.route("/size")
def size():
    """Return how much memory we're taking.

    Doesn't work if you're running with Gunicorn because it makes child processes.
    """
    try:
        import psutil
    except ImportError:
        return jsonify({})
    process = psutil.Process(os.getpid())
    n_bytes = process.memory_info().rss  # in bytes
    return jsonify(
        n_bytes=n_bytes,
        n_bytes_human=naturalsize(n_bytes),
    )


def get_app(
    name_data: Union[None, str, pd.DataFrame] = None,
    alts_data: Union[None, str, pd.DataFrame] = None,
    defs_data: Union[None, str, pd.DataFrame] = None,
    lazy: bool = False,
    sql: bool = False,
    uri: Optional[str] = None,
    refs_table: Optional[str] = None,
    alts_table: Optional[str] = None,
    defs_table: Optional[str] = None,
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
    Swagger(
        app,
        merge=True,
        config={
            "title": "Bioresolver API",
            "description": "Resolves CURIEs to their names, definitions, and other attributes.",
            "contact": {
                "responsibleDeveloper": "Charles Tapley Hoyt",
                "email": "cthoyt@gmail.com",
            },
        },
    )
    Bootstrap(app)

    app.config["resolver_backend"] = _get_resolver(
        name_data=name_data,
        alts_data=alts_data,
        defs_data=defs_data,
        lazy=lazy,
        sql=sql,
        uri=uri,
        refs_table=refs_table,
        alts_table=alts_table,
        defs_table=defs_table,
    )
    app.register_blueprint(resolve_blueprint)

    @app.before_first_request
    def before_first_request():
        logger.info("before_first_request")
        backend.count_prefixes()
        backend.count_alts()
        backend.count_names()

    return app


def _get_resolver(
    name_data: Union[None, str, pd.DataFrame] = None,
    alts_data: Union[None, str, pd.DataFrame] = None,
    defs_data: Union[None, str, pd.DataFrame] = None,
    lazy: bool = False,
    sql: bool = False,
    uri: Optional[str] = None,
    refs_table: Optional[str] = None,
    alts_table: Optional[str] = None,
    defs_table: Optional[str] = None,
) -> Backend:
    if sql:
        logger.info("using raw SQL backend")
        return RawSQLBackend(
            engine=uri,
            refs_table=refs_table,
            alts_table=alts_table,
            defs_table=defs_table,
        )

    if lazy:
        name_lookup = None
    elif name_data is None:
        name_lookup = _get_lookup_from_path(ensure_ooh_na_na())
    elif isinstance(name_data, str):
        name_lookup = _get_lookup_from_path(name_data)
    elif isinstance(name_data, pd.DataFrame):
        name_lookup = _get_lookup_from_df(name_data)
    else:
        raise TypeError(f"invalid type for `name_data`: {name_data}")

    if lazy:
        alts_lookup = None
    elif alts_data is None and not lazy:
        alts_lookup = _get_lookup_from_path(ensure_alts())
    elif isinstance(alts_data, str):
        alts_lookup = _get_lookup_from_path(alts_data)
    elif isinstance(alts_data, pd.DataFrame):
        alts_lookup = _get_lookup_from_df(alts_data)
    else:
        raise TypeError(f"invalid type for `alt_data`: {alts_data}")

    if lazy:
        defs_lookup = None
    elif defs_data is None and not lazy:
        defs_lookup = _get_lookup_from_path(ensure_definitions())
    elif isinstance(defs_data, str):
        defs_lookup = _get_lookup_from_path(defs_data)
    elif isinstance(defs_data, pd.DataFrame):
        defs_lookup = _get_lookup_from_df(defs_data)
    else:
        raise TypeError(f"invalid type for `defs_data`: {defs_data}")

    return _prepare_backend_with_lookup(
        name_lookup=name_lookup,
        alts_lookup=alts_lookup,
        defs_lookup=defs_lookup,
    )


def _prepare_backend_with_lookup(
    name_lookup: Optional[Mapping[str, Mapping[str, str]]] = None,
    alts_lookup: Optional[Mapping[str, Mapping[str, str]]] = None,
    defs_lookup: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> Backend:
    get_id_name_mapping, summarize_names = _h(name_lookup, pyobo.get_id_name_mapping)
    get_alts_to_id, summarize_alts = _h(alts_lookup, pyobo.get_alts_to_id)
    get_id_definition_mapping, summarize_definitions = _h(
        defs_lookup, pyobo.get_id_definition_mapping
    )

    return MemoryBackend(
        get_id_name_mapping=get_id_name_mapping,
        get_alts_to_id=get_alts_to_id,
        get_id_definition_mapping=get_id_definition_mapping,
        summarize_names=summarize_names,
        summarize_alts=summarize_alts,
        summarize_definitions=summarize_definitions,
    )


def _h(lookup, alt_lookup):
    if lookup is None:  # lazy mode, will download/cache data as needed
        return alt_lookup, Counter

    def _summarize():
        return Counter({k: len(v) for k, v in lookup.items()})

    return lookup.get, _summarize


def _get_lookup_from_df(df: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
    lookup = defaultdict(dict)
    it = tqdm(df.values, total=len(df.index), desc="loading mappings", unit_scale=True)
    for prefix, identifier, name in it:
        lookup[prefix][identifier] = name
    return dict(lookup)


def _get_lookup_from_path(path: Union[str, Path]) -> Mapping[str, Mapping[str, str]]:
    lookup = defaultdict(dict)
    with gzip.open(path, "rt") as file:
        _ = next(file)
        for line in tqdm(file, desc="loading mappings", unit_scale=True):
            prefix, identifier, name = line.strip().split("\t")
            lookup[prefix][identifier] = name
    return dict(lookup)
