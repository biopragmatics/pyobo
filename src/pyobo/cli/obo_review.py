# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.3.1",
#     "obographs>=0.0.8",
#     "robot-obo-tool>=0.0.1",
#     "ssslm>=0.1.3",
#     "tabulate>=0.9.0",
#     "tqdm>=4.67.3",
# ]
# ///

"""Implement lexical review for an ontology."""

import tempfile
from pathlib import Path

import click
import obographs
import robot_obo_tool
import ssslm
from tabulate import tabulate
from tqdm import tqdm

INDEX_URL = "https://github.com/biopragmatics/biolexica/raw/main/lexica/obo/obo.ssslm.tsv.gz"


@click.command()
@click.argument("obo_prefix")
@click.option(
    "--ontology-path",
    help="Local path to an OBO Graph JSON file. If not given, will try and look up through the OBO PURL system",
)
@click.option(
    "--uri-prefix",
    help="Local path to an OBO Graph JSON file. If not given, will try and look up through the OBO PURL system",
)
def obo_review(obo_prefix: str, ontology_path: str, uri_prefix: str) -> None:
    """Make a lexical review of an ontology."""
    graph_document = _get_graph_document(
        obo_prefix=obo_prefix,
        uri_prefix=uri_prefix,
        ontology_path=ontology_path,
    )

    click.echo(f"Loading lexical index from {INDEX_URL} using SSSLM")
    grounder = ssslm.make_grounder(INDEX_URL)

    passed, failed = do_it(graph_document=graph_document, matcher=grounder, uri_prefix=uri_prefix)

    if passed:
        click.echo(f"## Passed Nodes\n\n{tabulate(passed, headers=['LUID', 'Name'])}\n")

    if failed:
        click.echo("## Failed Nodes")
        for luid, name, matches in failed:
            click.echo(f"- f`{obo_prefix}:{luid}` {name}")
            for match in matches:
                curie = match.curie
                click.echo(
                    f"  - [`{curie}`](https://semantic.farm/{curie}) {match.name} ({round(match.score, 3)})"
                )


def _get_graph_document(
    obo_prefix: str, uri_prefix: str | None = None, ontology_path: str | None = None
) -> obographs.GraphDocument:
    if uri_prefix is None:
        uri_prefix = f"http://purl.obolibrary.org/obo/{obo_prefix}_"
        click.echo(f"Inferred URI prefix from given OBO CURIE prefix: {uri_prefix}")
    if ontology_path is None:
        ontology_path = f"https://purl.obolibrary.org/obo/{obo_prefix.lower()}.json"
        click.echo(f"No ontology path given, guessing it's available at {ontology_path}")
    if ontology_path.endswith(".json"):
        click.echo(f"reading OBO Graph JSON from {ontology_path}")
        return obographs.read(ontology_path, squeeze=False, timeout=60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir).joinpath("temp.json")
        click.echo(
            "given ontology path does not end with JSON. implicitly converting to OBO Graph JSON using ROBOT"
        )

        robot_obo_tool.convert(
            input_path=ontology_path,
            output_path=tmppath,
            check=False,
            merge=False,
            reason=False,
        )
        click.echo("reading converted OBO Graph JSON")
        return obographs.read(tmppath, squeeze=False)


def do_it(
    graph_document: obographs.GraphDocument,
    matcher: ssslm.Matcher,
    uri_prefix: str,
) -> tuple[list[tuple[str, str]], list[tuple[str, str, list[ssslm.Match]]]]:
    """Get matches."""
    passed = []
    failed = []
    for graph in tqdm(graph_document.graphs, unit="graph"):
        for node in tqdm(sorted(graph.nodes, key=lambda n: n.id), unit="node", leave=False):
            if not node.id.startswith(uri_prefix) or not node.lbl:
                continue

            local_unique_identifier = node.id[len(uri_prefix) :]

            matches = []
            matches.extend(matcher.get_matches(node.lbl))
            if node.meta is not None and node.meta.synonyms is not None:
                matches.extend(
                    match
                    for synonym in node.meta.synonyms
                    for match in matcher.get_matches(synonym.val)
                )

            if not matches:
                passed.append((local_unique_identifier, node.lbl))
            else:
                failed.append((local_unique_identifier, node.lbl, matches))
    return passed, failed


if __name__ == "__main__":
    obo_review()
