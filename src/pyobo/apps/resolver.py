# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service."""

import gzip
from collections import defaultdict
from typing import Optional, Union

import click
import pandas as pd
from flask import Blueprint, Flask, current_app, jsonify, url_for
from tqdm import tqdm
from werkzeug.local import LocalProxy

from pyobo.cli_utils import verbose_option
from pyobo.identifier_utils import normalize_curie

resolve_blueprint = Blueprint('resolver', __name__)

REMOTE_DATA_URL = 'https://zenodo.org/record/3756206/files/ooh_na_na.tsv.gz'

get_name = LocalProxy(lambda: current_app.config['get_name'])


@resolve_blueprint.route('/')
def home():
    """Serve the home page."""
    success = url_for(
        f'.{resolve.__name__}',
        curie='DOID:14330',
    )
    remapped = url_for(
        f'.{resolve.__name__}',
        curie='do:14330',
    )
    failure = url_for(
        f'.{resolve.__name__}',
        curie='DOID:00000',
    )

    return f'''
    <h1>PyOBO Resolver</h1>
    <ul>
    <li>Example successful lookup: <a href="{success}">{success}</a></li>
    <li>Example successful lookup by remapping prefix: <a href="{remapped}">{remapped}</a></li>
    <li>Example unsuccessful lookup: <a href="{failure}">{failure}</a></li>
    </ui>
    '''


@resolve_blueprint.route('/resolve/<curie>')
def resolve(curie: str):
    """Resolve a CURIE."""
    prefix, identifier = normalize_curie(curie)
    if prefix is None:
        return jsonify(
            query=curie,
            success=False,
            message='Could not identify prefix',
        )

    name = get_name(prefix, identifier)
    if name is None:
        return jsonify(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            success=False,
            message='Could not look up identifier',
        )

    return jsonify(
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

    if data is None:
        import pyobo.extract
        app.config['get_name'] = pyobo.extract.get_name
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

        def _get_name(_prefix: str, _identifier: str) -> Optional[str]:
            return lookup.get(_prefix, {}).get(identifier)

        app.config['get_name'] = _get_name

    app.register_blueprint(resolve_blueprint)
    return app


@click.command()
@click.option('--port', type=int)
@click.option('--host')
@click.option('--data')
@verbose_option
def main(port: int, host: str, data: Optional[str]):
    """Run the resolver app."""
    app = get_app(data)
    app.run(port=port, host=host)


if __name__ == '__main__':
    main()
