# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service."""

import click
from flask import Blueprint, Flask, jsonify, url_for

from pyobo.extract import get_name
from pyobo.identifier_utils import normalize_curie

resolve_blueprint = Blueprint('resolver', __name__)


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


def get_app() -> Flask:
    """Build a flask app."""
    app = Flask(__name__)
    app.register_blueprint(resolve_blueprint)
    return app


@click.command()
@click.option('--port')
@click.option('--host', type=int)
def main(port: str, host: int):
    """Run the resolver app."""
    app = get_app()
    app.run(port=port, host=host)


if __name__ == '__main__':
    main()
