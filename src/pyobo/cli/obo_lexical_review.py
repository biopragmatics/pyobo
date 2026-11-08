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

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    import obographs
    import ssslm

INDEX_URL = "https://github.com/biopragmatics/biolexica/raw/main/lexica/obo/obo.ssslm.tsv.gz"
UPPER = {"ncit"}


@click.command(
    help="""\

For OBO Foundry ontologies, it's sufficient to pass just --prefix, which
automatically looks up the download location and URI prefix from the
Bioregistry

$ pyobo obo-lexical-review --prefix go

For non-OBO Foundry ontologies, there isn't necessarily a URI prefix
or location in the Bioregistry, so pass them explicitly.

\b
$ pyobo obo-lexical-review \\
    --prefix sio \\
    --uri-prefix "http://semanticscience.org/resource/SIO_" \\
    --location http://semanticscience.org/ontology/sio/v1.59/sio-release.owl

When being explicit about the --uri-prefix and --location, the prefix is actually optional,
and even resources not registered in the Bioregistry can be used:

\b
$ pyobo obo-lexical-review \\
    --uri-prefix https://w3id.org/euph/ \\
    --location https://gitlab.com/bee-life/controlled-vocabulary/-/raw/V1.4/PolOn_V.1.4_rdf-xml.owl
"""
)
@click.option(
    "--prefix",
    help="The optional prefix, for looking up the --location and/or --uri-prefix in the Semantic Farm/Bioregistry",
)
@click.option(
    "--location",
    help="Local path or URL to an OBO Graph JSON file or OWL file. If not given, will try and look up through the OBO PURL system",
)
@click.option(
    "--uri-prefix",
    help="The URI prefix to use to identify terms that belong to the graph. If not given, "
    "assumes that the URI prefix should be constructed as an OBO PURL like "
    "`http://purl.obolibrary.org/obo/<prefix>_`.",
)
@click.option(
    "--index-url",
    default=INDEX_URL,
    show_default=True,
    help="Define an alternate term index. Note, this gets cached locally. Big ones take a few minutes to load.",
)
@click.option(
    "--show-passed", is_flag=True, help="Output statistics about passing terms to the console"
)
@click.option(
    "--skip-upper",
    is_flag=True,
    help=f"if true, skip matching to upper level ontologies {UPPER}, which are often false positives (or unhelpful for review)",
)
@click.option("--index-force", is_flag=True, help="if true, force re-downloading the lexical index")
def obo_lexical_review(
    prefix: str | None,
    location: str | None,
    uri_prefix: str | None,
    index_url: str,
    show_passed: bool,
    skip_upper: bool,
    index_force: bool,
) -> None:
    """Make a lexical review of an ontology."""
    import sys
    import time

    import pyperclip
    import pystow
    import ssslm
    from tabulate import tabulate

    module = pystow.module("pyobo", "obo-lexical-review")

    args = " ".join(sys.argv[1:])
    output = f'Analysis run on {time.asctime()} with the following command:\n\n```console\n$ uv tool run --with "pyobo[gilda]" pyobo obo-lexical-review {args}\n```\n\n'

    graph_document, uri_prefix = _get_graph_document(
        prefix=prefix,
        uri_prefix=uri_prefix,
        location=location,
    )

    click.echo(f"Loading lexical index from {index_url} using SSSLM")
    path = module.ensure(url=index_url, force=index_force)
    grounder = ssslm.make_grounder(path, progress=True)
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
            rows,
            headers=[prefix or "ID", "name", "obo-curie", "obo-name", "obo-score"],
            tablefmt="github",
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
    prefix: str | None, uri_prefix: str | None = None, location: str | None = None
) -> tuple[obographs.GraphDocument, str]:
    from pathlib import Path

    import obographs
    import robot_obo_tool
    from bioregistry import manager

    if uri_prefix is None:
        if prefix is None:
            raise click.ClickException(
                "either pass --uri-prefix or pass --prefix to try to automatically look it up in the Semantic Farm/Bioregistry"
            )
        if (resource := manager.get_resource(prefix)) is None:
            raise click.ClickException(
                f"can't automatically look up URI prefix unregistered resource: {prefix}. pass --uri-prefix"
            )
        if (obo_prefix := resource.get_obofoundry_prefix()) is None:
            raise click.ClickException(
                f"{prefix} is not an OBO Foundry resource, so --uri-prefix and --location are required"
            )
        uri_prefix = f"http://purl.obolibrary.org/obo/{obo_prefix}_"
        click.echo(f"Inferred URI prefix from given OBO CURIE prefix: {uri_prefix}")

    if location is None:
        if prefix is None:
            raise click.ClickException(
                "either pass --location or pass --prefix to try to automatically look it up in the Semantic Farm/Bioregistry"
            )
        if (resource := manager.get_resource(prefix)) is None:
            raise click.ClickException(
                f"can't automatically look up ontology URL for unregistered resource: {prefix}. pass --location"
            )
        if (obo_prefix := resource.get_obofoundry_prefix()) is None:
            raise click.ClickException(
                f"{prefix} is not an OBO Foundry resource, so --uri-prefix and --location are required"
            )
        # raise error if there's no mapping from prefix to OBO
        location = f"https://purl.obolibrary.org/obo/{obo_prefix.lower()}.json"
        click.echo(f"No ontology path given, guessing it's available at {location}")

    if location.endswith(".json"):
        click.echo(f"reading OBO Graph JSON from {location}")
        graph_documents = obographs.read(location, squeeze=False, timeout=60)
    else:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir).joinpath("temp.json")
            click.echo(
                "given ontology path does not end with JSON. implicitly converting to OBO Graph JSON using ROBOT"
            )
            robot_obo_tool.convert(
                input_path=location,
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
                    if synonym.val and synonym.val.strip()
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
