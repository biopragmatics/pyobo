import subprocess
import tempfile
from pathlib import Path

import click

import ssslm
import obographs
import sys
import bioregistry
from tqdm import tqdm
from pystow.utils import name_from_url, download
import robot_obo_tool

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

    for label, url in [("OWL", bioregistry.get_owl_download(prefix)), ("OBO", bioregistry.get_obo_download(prefix))]:
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
@click.option("--obograph-path",
              help="Local path to an OBO Graph JSON file. If not given, will try and look up through the OBO PURL system")
def obo_review(obo_prefix: str, obograph_path: str) -> None:
    """Make a lexical review of an ontology."""
    obo_uri_prefix = f"http://purl.obolibrary.org/obo/{obo_prefix}_"
    if obograph_path is None:
        obograph_path = f"https://purl.obolibrary.org/obo/{obo_prefix.lower()}.json"

    click.echo(f"Loading lexical index from {INDEX_URL} using SSSLM")
    grounder = ssslm.make_grounder(INDEX_URL)

    safe = []

    for graph in graph_document.graphs:
        for node in sorted(graph.nodes, key=lambda n: n.id):
            if not node.id.startswith(obo_uri_prefix):
                continue

            # Skip nodes without a label
            name = node.lbl
            if not name:
                continue

            local_unique_identifier = node.id[len(obo_uri_prefix):]

            matches = []
            matches.extend(grounder.get_matches(name))
            matches.extend(
                match
                for synonym in node.get("meta", {}).get("synonyms", [])
                for match in grounder.get_matches(synonym['val'])
            )

            if not matches:
                safe.append((local_unique_identifier, name))
            else:
                print(f'- f`{obo_prefix}:{local_unique_identifier}`', name)
            for match in matches:
                curie = match.curie
                print(f'  - [`{curie}`](https://bioregistry.io/{curie}) {match.name} ({round(match.score, 3)})')

    for local_unique_identifier, name in safe:
        click.echo(f'- `{obo_prefix}:{local_unique_identifier}`', name)


if __name__ == '__main__':
    obo_review()
