# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service.

Run with ``python -m pyobo.apps.resolver``
"""

import gzip
import os
from collections import Counter, defaultdict
from typing import Any, Mapping, Optional, Union
from urllib.request import urlretrieve

import click
import pandas as pd
import psutil
from flasgger import Swagger
from flask import Blueprint, Flask, current_app, jsonify, render_template
from flask_bootstrap import Bootstrap
from humanize.filesize import naturalsize
from tqdm import tqdm
from werkzeug.local import LocalProxy

import pyobo
from pyobo.apps.utils import gunicorn_option, host_option, port_option, run_app
from pyobo.cli_utils import verbose_option
from pyobo.constants import PYOBO_HOME
from pyobo.identifier_utils import get_identifiers_org_link, normalize_curie

resolve_blueprint = Blueprint('resolver', __name__)

REMOTE_DATA_URL = 'https://zenodo.org/record/3866538/files/ooh_na_na.tsv.gz'

get_id_name_mapping = LocalProxy(lambda: current_app.config['get_id_name_mapping'])
get_summary = LocalProxy(lambda: current_app.config['summarize'])


@resolve_blueprint.route('/')
def home():
    """Serve the home page."""
    return render_template('home.html')


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
    return jsonify(_help_resolve(curie))


@resolve_blueprint.route('/summary')
def summary():
    """Summary of the content in the service."""
    return jsonify(get_summary())


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


def _help_resolve(curie: str) -> Mapping[str, Any]:
    prefix, identifier = normalize_curie(curie)
    if prefix is None:
        return dict(
            query=curie,
            success=False,
            message='Could not identify prefix',
        )

    miriam = get_identifiers_org_link(prefix, identifier)

    id_name_mapping = get_id_name_mapping(prefix)
    if id_name_mapping is None:
        rv = dict(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            success=False,
        )
        if miriam:
            rv.update(dict(
                miriam=miriam,
                message='Could not find id->name mapping for prefix, but still able to report Identifiers.org link',
            ))
        else:
            rv['message'] = 'Could not find id->name mapping for prefix'
        return rv

    name = id_name_mapping.get(identifier)
    if name is None:
        return dict(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            success=False,
            message='Could not look up identifier',
        )

    return dict(
        query=curie,
        prefix=prefix,
        identifier=identifier,
        name=name,
        success=True,
        miriam=miriam,
    )


def get_app(data: Union[None, str, pd.DataFrame] = None, lazy: bool = False) -> Flask:
    """Build a flask app.

    :param data: If none, uses the internal PyOBO loader. If a string, assumes is a gzip and reads a
     dataframe from there. If a dataframe, uses it directly. Assumes data frame has 3 columns - prefix,
     identifier, and name and is a TSV.
    :param lazy: don't load the full cache into memory to run
    """
    app = Flask(__name__)
    Swagger(app)
    Bootstrap(app)

    if data is None and lazy:
        app.config['get_id_name_mapping'] = pyobo.get_id_name_mapping
        app.config['summarize'] = lambda: Counter({})
    if data is None and not lazy:
        path = os.path.join(PYOBO_HOME, 'ooh_na_na.tsv.gz')
        if not os.path.exists(path):
            urlretrieve(REMOTE_DATA_URL, path)
        lookup = _get_lookup_from_path(path)
        _prepare_app_with_lookup(app, lookup)
    elif isinstance(data, str):
        lookup = _get_lookup_from_path(data)
        _prepare_app_with_lookup(app, lookup)
    elif isinstance(data, pd.DataFrame):
        lookup = _get_lookup_from_df(data)
        _prepare_app_with_lookup(app, lookup)
    else:
        raise TypeError(f'invalid type: {data}')

    app.register_blueprint(resolve_blueprint)
    return app


def _prepare_app_with_lookup(app: Flask, lookup: Mapping[str, Mapping[str, str]]) -> None:
    app.config['get_id_name_mapping'] = lookup.get
    app.config['summarize'] = lambda: Counter({k: len(v) for k, v in lookup.items()})


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
@click.option('--lazy', is_flag=True, help='do no load full cache into memory automatically')
@click.option('--test', is_flag=True, help='run in test mode with only a few datasets')
@gunicorn_option
@verbose_option
def main(port: int, host: str, data: Optional[str], test: bool, gunicorn: bool, lazy: bool):
    """Run the resolver app."""
    if test:
        data = [
            (prefix, identifier, name)
            for prefix in ['hgnc', 'chebi', 'doid']
            for identifier, name in pyobo.get_id_name_mapping(prefix).items()
        ]
        data = pd.DataFrame(data, columns=['prefix', 'identifier', 'name'])

    app = get_app(data, lazy=lazy)
    run_app(app=app, host=host, port=port, gunicorn=gunicorn)


if __name__ == '__main__':
    main()
