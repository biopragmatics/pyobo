# -*- coding: utf-8 -*-

"""PyOBO's Mapping Service."""

from functools import lru_cache
from typing import Iterable, List, Mapping, Optional, Union

import click
import pandas as pd
from flask import Blueprint, Flask, current_app, jsonify, url_for
from werkzeug import LocalProxy

from pyobo.xrefdb.xrefs_pipeline import (
    all_shortest_paths, get_graph_from_xref_df, get_xref_df,
    single_source_shortest_path,
)

__all__ = [
    'get_app',
    'main',
]

graph = LocalProxy(lambda: current_app.config['graph'])


@lru_cache()
def _single_source_shortest_path(curie: str) -> Optional[Mapping[str, List[Mapping[str, str]]]]:
    return single_source_shortest_path(graph=graph, curie=curie)


@lru_cache()
def _all_shortest_paths(source_curie: str, target_curie: str) -> List[List[Mapping[str, str]]]:
    return all_shortest_paths(graph=graph, source_curie=source_curie, target_curie=target_curie)


#: The blueprint that gets added to the app.s
search_blueprint = Blueprint('search', __name__)


@search_blueprint.route('/')
def home():
    """Show the home page."""
    example_url_1 = url_for(
        single_source_mappings.__name__,
        curie='hgnc:6893',
    )
    example_url_2 = url_for(
        all_mappings.__name__,
        source_curie='hgnc:6893',
        target_curie='ensembl:ENSMUSP00000102605',
    )
    return f'''Use the /mappings endpoint. For example, <a href="{example_url_1}">{example_url_1}</a> or
        <a href="{example_url_2}">{example_url_2}</a>/
        '''


@search_blueprint.route('/mappings/<curie>')
def single_source_mappings(curie: str):
    """Return all length xrefs from the given identifier."""
    if curie not in graph:
        return jsonify(
            success=False,
            query=dict(curie=curie),
            message='could not find curie',
        )
    return jsonify(_single_source_shortest_path(curie))


@search_blueprint.route('/mappings/<source_curie>/<target_curie>')
def all_mappings(source_curie: str, target_curie: str):
    """Return all shortest paths of xrefs between the two identifiers."""
    if source_curie not in graph:
        return jsonify(
            success=False,
            query=dict(source_curie=source_curie, target_curie=target_curie),
            message='could not find source curie',
        )
    if target_curie not in graph:
        return jsonify(
            success=False,
            query=dict(source_curie=source_curie, target_curie=target_curie),
            message='could not find target curie',
        )

    return jsonify(_all_shortest_paths(source_curie, target_curie))


def get_app(paths: Union[None, str, Iterable[str]] = None) -> Flask:
    """Build the Flask app."""
    if paths is None:
        df = get_xref_df()
    elif isinstance(paths, str):
        df = pd.read_csv(paths, sep='\t', dtype=str)
    else:
        df = pd.concat(
            pd.read_csv(path, sep='\t', dtype=str)
            for path in paths
        )
    return _get_app_from_xref_df(df)


def _get_app_from_xref_df(df: pd.DataFrame):
    app = Flask(__name__)
    app.config['graph'] = get_graph_from_xref_df(df)
    app.register_blueprint(search_blueprint)
    return app


@click.command()
@click.option('-m', '--mappings-file', multiple=True, default=['/Users/cthoyt/Desktop/xrefs.tsv.gz'])
@click.option('--port')
@click.option('--host', type=int)
def main(mappings_file, port: str, host: int):
    """Run the mappings app."""
    app = get_app(mappings_file)
    app.run(port=port, host=host)


if __name__ == '__main__':
    main()
