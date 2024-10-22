"""CLI for PyOBO."""

import logging
import os
import sys
from operator import itemgetter

import click
import humanize
from more_click import verbose_option
from tabulate import tabulate

from .aws import main as aws_main
from .database import main as database_main
from .lookup import lookup
from ..constants import RAW_DIRECTORY
from ..plugins import has_nomenclature_plugin, iter_nomenclature_plugins
from ..registries import iter_cached_obo
from ..utils.io import get_writer
from ..xrefdb.canonicalizer import Canonicalizer, get_priority_curie, remap_file_stream
from ..xrefdb.priority import DEFAULT_PRIORITY_LIST

__all__ = ["main"]

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main():
    """CLI for PyOBO."""


_ORDERING_TEXT = ", ".join(f"{i}) {x}" for i, x in enumerate(DEFAULT_PRIORITY_LIST, start=1))


@main.command(help=f"Prioritize a CURIE from ordering: {_ORDERING_TEXT}")
@click.argument("curie")
def prioritize(curie: str):
    """Prioritize a CURIE."""
    priority_curie = get_priority_curie(curie)
    click.secho(priority_curie)


@main.command()
@click.option("-i", "--file-in", type=click.File("r"), default=sys.stdin)
@click.option("-o", "--file-out", type=click.File("w"), default=sys.stdout)
@click.option("--column", type=int, default=0, show_default=True)
@click.option("--sep", default="\t", show_default=True)
def recurify(file_in, file_out, column: int, sep: str):
    """Remap a column in a given file stream."""
    remap_file_stream(file_in=file_in, file_out=file_out, column=column, sep=sep)


@main.command()
@verbose_option
def cache():
    """Cache all resources."""
    for obo in iter_nomenclature_plugins():
        click.secho(f"Caching {obo.ontology}", bold=True, fg="green")
        obo.write_default()


@main.command()
@click.option("--remove-obo", is_flag=True)
def clean(remove_obo: bool):
    """Delete all cached files."""
    suffixes = [
        "_mappings.tsv",
        ".mapping.tsv",
        "_synonyms.tsv",
        ".obo.pickle",
        ".obo.json.gz",
        ".owl",
    ]
    if remove_obo:
        suffixes.append(".obo")
    for directory in os.listdir(RAW_DIRECTORY):
        d = os.path.join(RAW_DIRECTORY, directory)
        if not os.path.isdir(d):
            continue
        entities = list(os.listdir(d))
        if not entities:
            os.rmdir(d)
        obo_pickle = os.path.join(d, f"{directory}.obo.pickle")
        if os.path.exists(obo_pickle):
            os.remove(obo_pickle)
        for f in entities:
            if any(f.endswith(suffix) for suffix in suffixes):
                os.remove(os.path.join(d, f))


@main.command()
def ls():
    """List how big all of the OBO files are."""
    entries = [(prefix, os.path.getsize(path)) for prefix, path in iter_cached_obo()]
    entries = [
        (prefix, humanize.naturalsize(size), "✅" if not has_nomenclature_plugin(prefix) else "❌")
        for prefix, size in sorted(entries, key=itemgetter(1), reverse=True)
    ]
    click.echo(tabulate(entries, headers=["Source", "Size", "OBO"]))


@main.command()
@verbose_option
@click.option("-f", "--file", type=click.File("w"))
def remapping(file):
    """Make a canonical remapping."""
    canonicalizer = Canonicalizer.get_default()
    writer = get_writer(file)
    writer.writerow(["input", "canonical"])
    writer.writerows(canonicalizer.iterate_flat_mapping())


main.add_command(lookup)
main.add_command(aws_main)
main.add_command(database_main)

if __name__ == "__main__":
    main()
