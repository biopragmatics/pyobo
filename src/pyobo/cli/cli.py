"""CLI for PyOBO."""

import logging
import os
from collections.abc import Iterable
from functools import lru_cache
from operator import itemgetter

import bioregistry
import click
import humanize
from tabulate import tabulate

from .database import main as database_main
from .lookup import lookup
from ..constants import GLOBAL_SKIP, RAW_DIRECTORY
from ..plugins import has_nomenclature_plugin

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
    entries = [(prefix, os.path.getsize(path)) for prefix, path in _iter_cached_obo()]
    entries = [
        (prefix, humanize.naturalsize(size), "✅" if not has_nomenclature_plugin(prefix) else "❌")
        for prefix, size in sorted(entries, key=itemgetter(1), reverse=True)
    ]
    click.echo(tabulate(entries, headers=["Source", "Size", "OBO"]))


def _iter_cached_obo() -> Iterable[tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(RAW_DIRECTORY):
        if prefix in GLOBAL_SKIP or _has_no_download(prefix) or bioregistry.is_deprecated(prefix):
            continue
        d = RAW_DIRECTORY.joinpath(prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith(".obo"):
                p = os.path.join(d, x)
                yield prefix, p


def _has_no_download(prefix: str) -> bool:
    """Return if the prefix is not available."""
    prefix_norm = bioregistry.normalize_prefix(prefix)
    return prefix_norm is not None and prefix_norm in _no_download()


@lru_cache(maxsize=1)
def _no_download() -> set[str]:
    """Get the list of prefixes not available as OBO."""
    return {
        prefix
        for prefix in bioregistry.read_registry()
        if bioregistry.get_obo_download(prefix) is None
        and bioregistry.get_owl_download(prefix) is None
    }


main.add_command(lookup)
main.add_command(database_main)

if __name__ == "__main__":
    main()
