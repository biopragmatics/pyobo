# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bioregistry>=0.13.18",
#     "click>=8.3.1",
#     "obographs>=0.0.8",
#     "pystow>=0.7.21",
#     "robot-obo-tool>=0.0.1",
#     "ssslm>=0.1.3",
#     "tabulate>=0.9.0",
#     "tqdm>=4.67.3",
# ]
# ///

"""Implement lexical review for an ontology."""

import subprocess
import tempfile
from pathlib import Path

import bioregistry
import click
import obographs
import robot_obo_tool
import ssslm
from pystow.utils import download, name_from_url
from tabulate import tabulate
from tqdm import tqdm

INDEX_URL = "https://github.com/biopragmatics/biolexica/raw/main/lexica/obo/obo.ssslm.tsv.gz"


def get_obograph_by_prefix(
    prefix: str,
    *,
    check: bool = True,
    reason: bool = False,
    merge: bool = False,
) -> obographs.GraphDocument:
    """Get an ontology by its Bioregistry prefix."""
    if prefix != bioregistry.normalize_prefix(prefix):
        raise ValueError(f"this function requires bioregistry canonical prefixes: {prefix}")

    if json_url := bioregistry.get_json_download(prefix):
        try:
            graph_document = obographs.read(json_url, squeeze=False)
        except (OSError, ValueError, TypeError) as e:
            msg = f"[{prefix}] could not parse JSON from {json_url}: {e}"
            tqdm.write(msg)
        else:
            return graph_document

    for label, url in [
        ("OWL", bioregistry.get_owl_download(prefix)),
        ("OBO", bioregistry.get_obo_download(prefix)),
    ]:
        if url is None:
            msg = f"[{prefix}] no {label} URL available"
            tqdm.write(msg)
            continue
        try:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d).joinpath(name_from_url(url))
                download(url, path=path)
                robot_obo_tool.convert(
                    input_path=url,
                    output_path=path,
                    check=check,
                    merge=merge,
                    reason=reason,
                )
                graph_document = obographs.read(path, squeeze=False)
        except (subprocess.CalledProcessError, KeyError):
            msg = f"[{prefix}] could not parse {label} from {url}"
            tqdm.write(msg)
            continue
        else:
            return graph_document

    raise ValueError


@click.command()
@click.argument("obo_prefix")
@click.option(
    "--obograph-path",
    help="Local path to an OBO Graph JSON file. If not given, will try and look up through the OBO PURL system",
)
def obo_review(obo_prefix: str, obograph_path: str) -> None:
    """Make a lexical review of an ontology."""
    uri_prefix = f"http://purl.obolibrary.org/obo/{obo_prefix}_"
    if obograph_path is None:
        obograph_path = f"https://purl.obolibrary.org/obo/{obo_prefix.lower()}.json"

    graph_document = get_obograph_by_prefix(obo_prefix)

    click.echo(f"Loading lexical index from {INDEX_URL} using SSSLM")
    grounder = ssslm.make_grounder(INDEX_URL)

    passed, failed = do_it(graph_document=graph_document, grounder=grounder, uri_prefix=uri_prefix)

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


def do_it(
    graph_document: obographs.GraphDocument,
    grounder: ssslm.Matcher,
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
            matches.extend(grounder.get_matches(node.lbl))
            if node.meta is not None and node.meta.synonyms is not None:
                matches.extend(
                    match
                    for synonym in node.meta.synonyms
                    for match in grounder.get_matches(synonym.val)
                )

            if not matches:
                passed.append((local_unique_identifier, node.lbl))
            else:
                failed.append((local_unique_identifier, node.lbl, matches))
    return passed, failed


if __name__ == "__main__":
    obo_review()
