# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.3.1",
#     "obographs>=0.0.8",
#     "pyperclip>=1.11.0",
#     "robot-obo-tool>=0.0.1",
#     "ssslm[gilda-slim]>=0.1.3",
#     "tabulate>=0.9.0",
#     "tqdm>=4.67.3",
# ]
# ///

"""Implement lexical review for an ontology."""

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    import obographs
    import ssslm

INDEX_URL = "https://github.com/biopragmatics/biolexica/raw/main/lexica/obo/obo.ssslm.tsv.gz"
UPPER = {"ncit"}


@click.command()
@click.argument("prefix")
@click.option(
    "--location",
    help="Local path or URL to an OBO Graph JSON file or OWL file. If not given, will try and look up through the OBO PURL system",
)
@click.option(
    "--uri-prefix",
    help="Local path to an OBO Graph JSON file. If not given, will try and look up through the OBO PURL system",
)
@click.option("--index-url", default=INDEX_URL, show_default=True)
@click.option("--show-passed", is_flag=True)
@click.option("--skip-upper", is_flag=True, help=f"if true, skip upper level ontologies {UPPER}")
def obo_lexical_review(
    prefix: str,
    location: str | None,
    uri_prefix: str | None,
    index_url: str,
    show_passed: bool,
    skip_upper: bool,
) -> None:
    """Make a lexical review of an ontology."""
    import sys
    import time

    import pyperclip
    import ssslm
    from tabulate import tabulate

    args = " ".join(sys.argv[1:])
    output = f"Analysis of {prefix} run on {time.asctime()} with the following command:\n\n```console\n$ uvx pyobo obo-lexical-review {args}\n```\n\n"
    click.echo(output)

    graph_document, uri_prefix = _get_graph_document(
        prefix=prefix,
        uri_prefix=uri_prefix,
        ontology_path=location,
    )

    click.echo(f"Loading lexical index from {index_url} using SSSLM")
    grounder = ssslm.make_grounder(index_url)
    click.echo("Done loading lexical index")

    passed, failed = _get_calls(
        graph_document=graph_document,
        matcher=grounder,
        uri_prefix=uri_prefix,
        skip_upper=skip_upper,
    )

    total = len(passed) + len(failed)

    if passed and show_passed:
        passed_table = tabulate(passed, headers=["LUID", "Name"], tablefmt="github")
        passed_msg = f"## Passed Nodes ({len(passed):,}/{total:,}; {len(passed) / total:.1%})\n\n{passed_table}\n\n"
        output += passed_msg

    if failed:
        rows = []
        for luid, name, matches in failed:
            rows.append((luid, name, *_parts(matches[0])))
            for match in matches[1:]:
                rows.append(("", "", *_parts(match)))
        failed_table = tabulate(
            rows, headers=[prefix, "name", "obo-curie", "obo-name", "obo-score"], tablefmt="github"
        )
        failed_message = f"## Failed Nodes ({len(failed):,}/{total:,}; {len(failed) / total:.1%})\n\n{failed_table}\n\n"
        output += failed_message

    click.echo(output)
    click.echo("Finished! automatically copied to the clipboard, e.g., for pasting into GitHub)")
    pyperclip.copy(output)


def _parts(match: ssslm.Match) -> tuple[str, str, float]:
    return (
        f"[`{match.curie}`](https://semantic.farm/{match.curie})",
        match.name or "",
        round(match.score, 3),
    )


def _get_graph_document(
    prefix: str, uri_prefix: str | None = None, ontology_path: str | None = None
) -> tuple[obographs.GraphDocument, str]:
    from pathlib import Path

    import obographs
    import robot_obo_tool

    if uri_prefix is None:
        uri_prefix = f"http://purl.obolibrary.org/obo/{prefix}_"
        click.echo(f"Inferred URI prefix from given OBO CURIE prefix: {uri_prefix}")
    if ontology_path is None:
        ontology_path = f"https://purl.obolibrary.org/obo/{prefix.lower()}.json"
        click.echo(f"No ontology path given, guessing it's available at {ontology_path}")
    if ontology_path.endswith(".json"):
        click.echo(f"reading OBO Graph JSON from {ontology_path}")
        graph_documents = obographs.read(ontology_path, squeeze=False, timeout=60)
    else:
        import tempfile

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
            graph_documents = obographs.read(tmppath, squeeze=False)

    return graph_documents, uri_prefix


def _get_calls(
    *,
    graph_document: obographs.GraphDocument,
    matcher: ssslm.Matcher,
    uri_prefix: str,
    skip_upper: bool = False,
) -> tuple[list[tuple[str, str]], list[tuple[str, str, list[ssslm.Match]]]]:
    """Get matches."""
    from tqdm import tqdm

    passed = []
    failed = []
    total = 0
    skipped = 0
    for graph in tqdm(graph_document.graphs, unit="graph"):
        for node in tqdm(sorted(graph.nodes, key=lambda n: n.id), unit="node", leave=False):
            if node.id is None:
                continue

            total += 1
            if not node.id.startswith(uri_prefix):
                skipped += 1
                continue

            if not node.lbl:
                continue

            local_unique_identifier = node.id[len(uri_prefix) :]

            matches: list[ssslm.Match] = []
            matches.extend(matcher.get_matches(node.lbl))
            if node.meta is not None and node.meta.synonyms is not None:
                matches.extend(
                    match
                    for synonym in node.meta.synonyms
                    for match in matcher.get_matches(synonym.val)
                )

            # there are a lot of NCIT matches, which aren't that informative
            # since OBO doesn't mind duplicating these terms
            if skip_upper:
                matches = [m for m in matches if m.prefix not in UPPER]

            if not matches:
                passed.append((local_unique_identifier, node.lbl))
            else:
                failed.append((local_unique_identifier, node.lbl, matches))

    return passed, failed


if __name__ == "__main__":
    obo_lexical_review()
