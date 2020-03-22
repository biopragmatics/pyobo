# -*- coding: utf-8 -*-

"""PyOBO's Mapping Service."""

import itertools as itt
from functools import lru_cache
from typing import Iterable, Union

import click
import networkx as nx
import pandas as pd
from flask import Flask, jsonify, url_for
from more_itertools import pairwise
from tqdm import tqdm

from pyobo.mappings.xrefs_pipeline import get_xref_df

__all__ = [
    'get_app',
    'main',
]


def _to_curie(prefix, identifier):
    return f'{prefix}:{identifier}'


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

    app = Flask(__name__)

    graph = nx.Graph()

    it = itt.chain(
        df[['source_ns', 'source_id']].drop_duplicates().values,
        df[['target_ns', 'target_id']].drop_duplicates().values,
    )
    it = tqdm(it, desc='loading curies', unit_scale=True)
    for prefix, identifier in it:
        graph.add_node(_to_curie(prefix, identifier), prefix=prefix, identifier=identifier)

    it = tqdm(df.values, total=len(df.index), desc='loading xrefs', unit_scale=True)
    for source_ns, source_id, target_ns, target_id, source in it:
        graph.add_edge(
            _to_curie(source_ns, source_id),
            _to_curie(target_ns, target_id),
            source=source,
        )

    # Unresponsive:
    # -------------
    # for curies in tqdm(nx.connected_components(graph), desc='filling connected components', unit_scale=True):
    #     for c1, c2 in itt.combinations(curies, r=2):
    #         if not graph.has_edge(c1, c2):
    #             graph.add_edge(c1, c2, inferred=True)

    # Way too slow:
    # -------------
    # for curie in tqdm(graph, total=graph.number_of_nodes(), desc='mapping connected components', unit_scale=True):
    #     for incident_curie in nx.node_connected_component(graph, curie):
    #         if not graph.has_edge(curie, incident_curie):
    #             graph.add_edge(curie, incident_curie, inferred=True)

    @lru_cache()
    def _single_source_shortest_path(curie: str):
        if curie not in graph:
            return None
        rv = nx.single_source_shortest_path(graph, curie)
        return {
            k: [
                dict(source=s, target=t, provenance=graph[s][t]['source'])
                for s, t in pairwise(v)
            ]
            for k, v in rv.items()
            if k != curie  # don't map to self
        }

    @lru_cache()
    def _all_shortest_paths(source_curie: str, target_curie: str):
        paths = nx.all_shortest_paths(graph, source=source_curie, target=target_curie)
        return [
            [
                dict(source=s, target=t, provenance=graph[s][t]['source'])
                for s, t in pairwise(v)
            ]
            for v in paths
        ]

    @app.route('/')
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

    @app.route('/mappings/<curie>')
    def single_source_mappings(curie: str):
        """Return all length xrefs from the given identifier."""
        if curie not in graph:
            return jsonify(
                success=False,
                query=dict(curie=curie),
                message='could not find curie',
            )
        return jsonify(_single_source_shortest_path(curie))

    @app.route('/mappings/<source_curie>/<target_curie>')
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

    return app
    # Also consider the condensation of the graph:
    # https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.condensation.html#networkx.algorithms.components.condensation


@click.command()
@click.option('-m', '--mappings-file', multiple=True, default=['/Users/cthoyt/Desktop/xrefs.tsv.gz'])
def main(mappings_file):
    """Run the mappings app."""
    app = get_app(mappings_file)
    app.run()


if __name__ == '__main__':
    main()
