# -*- coding: utf-8 -*-

"""PyOBO's Mapping Service.

Run with ``python -m pyobo.apps.mapper``.
"""

import os
from functools import lru_cache
from typing import Iterable, List, Mapping, Optional, Union

import click
import networkx as nx
import pandas as pd
from flasgger import Swagger
from flask import Blueprint, Flask, current_app, jsonify, render_template, url_for
from flask_bootstrap import Bootstrap
from werkzeug.local import LocalProxy

from pyobo.apps.utils import gunicorn_option, host_option, port_option, run_app
from pyobo.cli_utils import verbose_option
from pyobo.identifier_utils import normalize_curie, normalize_prefix
from pyobo.xrefdb.xrefs_pipeline import (
    Canonicalizer, all_shortest_paths, get_graph_from_xref_df, get_xref_df, single_source_shortest_path,
    summarize_xref_df,
)

__all__ = [
    'get_app',
    'main',
]

summary_df = LocalProxy(lambda: current_app.config['summary'])
graph: nx.Graph = LocalProxy(lambda: current_app.config['graph'])
canonicalizer: Canonicalizer = LocalProxy(lambda: current_app.config['canonicalizer'])


@lru_cache()
def _single_source_shortest_path(curie: str) -> Optional[Mapping[str, List[Mapping[str, str]]]]:
    return single_source_shortest_path(graph=graph, curie=curie)


@lru_cache()
def _all_shortest_paths(source_curie: str, target_curie: str) -> List[List[Mapping[str, str]]]:
    return all_shortest_paths(graph=graph, source_curie=source_curie, target_curie=target_curie)


#: The blueprint that gets added to the app
search_blueprint = Blueprint('search', __name__)


@search_blueprint.route('/')
def home():
    """Show the home page."""
    return render_template('mapper_home.html')


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


@search_blueprint.route('/mappings/summarize')
def summarize():
    """Summarize the mappings."""
    return summary_df.to_html(index=False)


@search_blueprint.route('/mappings/summarize_by/<prefix>')
def summarize_one(prefix: str):
    """Summarize the mappings."""
    prefix = normalize_prefix(prefix)
    in_df = summary_df.loc[summary_df['target_ns'] == prefix, ['source_ns', 'count']]
    out_df = summary_df.loc[summary_df['source_ns'] == prefix, ['target_ns', 'count']]
    return f'''
    <h1>Incoming Mappings to {prefix}</h1>
    {in_df.to_html(index=False)}
    <h1>Outgoing Mappings from {prefix}</h1>
    {out_df.to_html(index=False)}
    '''


@search_blueprint.route('/canonicalize/<curie>')
def canonicalize(curie: str):
    """Return the best CURIE."""
    # TODO maybe normalize the curie first?
    norm_prefix, norm_identifier = normalize_curie(curie)
    if norm_prefix is None or norm_identifier is None:
        return jsonify(
            query=curie,
            normalizable=False,
        )

    norm_curie = f'{norm_prefix}:{norm_identifier}'

    rv = dict(query=curie)
    if norm_curie != curie:
        rv['norm_curie'] = norm_curie

    if norm_curie not in graph:
        rv['found'] = False
    else:
        result_curie = canonicalizer.canonicalize(norm_curie)
        rv.update(
            found=True,
            result=result_curie,
            mappings=url_for(
                f'.{all_mappings.__name__}',
                source_curie=norm_curie,
                target_curie=result_curie,
            ),
        )

    return jsonify(rv)


def get_app(paths: Union[None, str, Iterable[str]] = None) -> Flask:
    """Build the Flask app."""
    if paths is None:
        paths = os.path.join(os.path.expanduser('~'), 'Desktop', 'all_xrefs.tsv')
        if os.path.exists(paths):
            df = pd.read_csv(paths, sep='\t', dtype=str)
        else:
            df = get_xref_df()
            df.to_csv(paths, sep='\t', index=False)
    elif isinstance(paths, str):
        df = pd.read_csv(paths, sep='\t', dtype=str)
    else:
        df = pd.concat(
            pd.read_csv(path, sep='\t', dtype=str)
            for path in paths
        )

    df['source_ns'] = df['source_ns'].map(normalize_prefix)
    df['target_ns'] = df['target_ns'].map(normalize_prefix)
    return _get_app_from_xref_df(df)


def _get_app_from_xref_df(df: pd.DataFrame):
    app = Flask(__name__)
    Swagger(app)
    Bootstrap(app)
    app.config['summary'] = summarize_xref_df(df)
    app.config['graph'] = get_graph_from_xref_df(df)
    # TODO allow for specification of priorities in the canonicalizer
    app.config['canonicalizer'] = Canonicalizer(graph=app.config['graph'])
    app.register_blueprint(search_blueprint)
    return app


@click.command()
@click.option('-x', '--mappings-file')
@port_option
@host_option
@gunicorn_option
@verbose_option
def main(mappings_file, host: str, port: int, gunicorn: bool):
    """Run the mappings app."""
    app = get_app(mappings_file)
    run_app(app=app, host=host, port=port, gunicorn=gunicorn)


if __name__ == '__main__':
    main()
