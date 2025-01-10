"""CLI for PyOBO."""

import logging
import os
from operator import itemgetter

import click
import humanize
from tabulate import tabulate

from .aws import main as aws_main
from .database import main as database_main
from .lookup import lookup
from ..constants import RAW_DIRECTORY
from ..plugins import has_nomenclature_plugin
from ..registries import iter_cached_obo

__all__ = ["main"]

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main():
    """CLI for PyOBO."""


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


main.add_command(lookup)
main.add_command(aws_main)
main.add_command(database_main)

if __name__ == "__main__":
    main()
