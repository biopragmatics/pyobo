# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service."""

from functools import lru_cache

import click
from flask import Blueprint, Flask, jsonify

from pyobo import get_id_name_mapping
from pyobo.identifier_utils import normalize_curie


@lru_cache()
def _get_id_name_mapping(prefix):
    return get_id_name_mapping(prefix)


resolve_blueprint = Blueprint('resolver', __name__)


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

    name = _get_id_name_mapping(prefix).get(identifier)
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
