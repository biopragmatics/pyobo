# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service."""

import gzip
from collections import Counter, defaultdict
from typing import Any, Mapping, Optional, Union

import click
import pandas as pd
from flasgger import Swagger
from flask import Blueprint, Flask, current_app, jsonify, render_template
from flask_bootstrap import Bootstrap
from tqdm import tqdm
from werkzeug.local import LocalProxy

import pyobo
from pyobo.cli_utils import verbose_option
from pyobo.identifier_utils import normalize_curie

resolve_blueprint = Blueprint('resolver', __name__)

REMOTE_DATA_URL = 'https://zenodo.org/record/3756206/files/ooh_na_na.tsv.gz'

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


def _help_resolve(curie: str) -> Mapping[str, Any]:
    prefix, identifier = normalize_curie(curie)
    if prefix is None:
        return dict(
            query=curie,
            success=False,
            message='Could not identify prefix',
        )

    id_name_mapping = get_id_name_mapping(prefix)
    if id_name_mapping is None:
        return dict(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            success=False,
            message='Could not find id->name mapping for prefix',
        )

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
    )


def get_app(data: Union[None, str, pd.DataFrame] = None) -> Flask:
    """Build a flask app.

    :param data: If none, uses the internal PyOBO loader. If a string, assumes is a gzip and reads a
     dataframe from there. If a dataframe, uses it directly. Assumes data frame has 3 columns - prefix,
     identifier, and name and is a TSV.
    """
    app = Flask(__name__)
    Swagger(app)
    Bootstrap(app)

    if data is None:
        app.config['get_id_name_mapping'] = pyobo.get_id_name_mapping
        app.config['summarize'] = lambda: Counter({})
    else:
        lookup = defaultdict(dict)

        if isinstance(data, str):
            with gzip.open(data, 'rt') as data:
                _ = next(data)
                for line in tqdm(data, desc='loading mappings', unit_scale=True):
                    prefix, identifier, name = line.strip().split('\t')
                    lookup[prefix][identifier] = name
        elif isinstance(data, pd.DataFrame):
            it = tqdm(data.values, total=len(data.index), desc='loading mappings', unit_scale=True)
            for prefix, identifier, name in it:
                lookup[prefix][identifier] = name
        else:
            raise TypeError(f'invalid type: {data}')

        lookup = dict(lookup)

        app.config['get_id_name_mapping'] = lookup.get
        app.config['summarize'] = lambda: Counter({k: len(v) for k, v in lookup.items()})

    app.register_blueprint(resolve_blueprint)
    return app


@click.command()
@click.version_option(version=pyobo.version.VERSION)
@click.option('--port', type=int, help='port on which the app is served')
@click.option('--host', help='host on which the app is run')
@click.option('--data', help='local 3-column gzipped TSV as database')
@click.option('--test', is_flag=True, help='run in test mode with only a few datasets')
@verbose_option
def main(port: int, host: str, data: Optional[str], test: bool):
    """Run the resolver app."""
    if test:
        data = [
            (prefix, identifier, name)
            for prefix in ['hgnc', 'chebi', 'doid']
            for identifier, name in pyobo.get_id_name_mapping(prefix).items()
        ]
        data = pd.DataFrame(data, columns=['prefix', 'identifier', 'name'])

    app = get_app(data)
    app.run(port=port, host=host)


if __name__ == '__main__':
    main()
