# -*- coding: utf-8 -*-

"""CLI for PyOBO Database Generation.

Run with ``obo database <subcommand>``.
"""

import os
from typing import Optional

import click
import pandas as pd

from .cli_utils import verbose_option
from .constants import DATABASE_DIRECTORY
from .getters import db_output_helper
from .xrefdb.xrefs_pipeline import _iter_alts, _iter_ooh_na_na, _iter_synonyms, get_xref_df, summarize_xref_df


@click.group()
def database():
    """Build the PyOBO Database."""


directory_option = click.option(
    '--directory',
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
)


@database.command()
@verbose_option
@directory_option
@click.pass_context
def build(ctx: click.Context, directory: str):
    """Build all databases."""
    click.secho('Alternate Identifiers', fg='cyan', bold=True)
    ctx.invoke(alts, directory=directory)
    click.secho('Synonyms', fg='cyan', bold=True)
    ctx.invoke(synonyms, directory=directory)
    click.secho('Xrefs', fg='cyan', bold=True)
    ctx.invoke(xrefs, directory=directory)
    click.secho('Names', fg='cyan', bold=True)
    ctx.invoke(names, directory=directory)
    # TODO relations


@database.command()
@verbose_option
@directory_option
@click.option('--no-strict', is_flag=True)
def names(directory: str, no_strict: bool):
    """Make the prefix-identifier-name dump."""
    db_output_helper(
        _iter_ooh_na_na,
        'names',
        ('prefix', 'identifier', 'name'),
        strict=not no_strict,
        directory=directory,
    )


@database.command()
@verbose_option
@directory_option
def alts(directory: str):
    """Make the prefix-alt-id dump."""
    db_output_helper(_iter_alts, 'alts', ('prefix', 'identifier', 'alt'), directory=directory)


@database.command()
@verbose_option
@directory_option
def synonyms(directory: str):
    """Make the prefix-identifier-synonym dump."""
    db_output_helper(_iter_synonyms, 'synonyms', ('prefix', 'identifier', 'synonym'), directory=directory)


@database.command()
@verbose_option
@directory_option
def xrefs(directory: str):  # noqa: D202
    """Make the prefix-identifier-xref dump."""
    xrefs_df = get_xref_df(rebuild=True, force=False)

    # Export all xrefs
    _write_tsv(xrefs_df, 'xrefs.tsv.gz', directory=directory)

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), 'xrefs_sample.tsv', directory=directory)

    # Export a summary dataframe
    summary_df = summarize_xref_df(xrefs_df)
    _write_tsv(summary_df, 'xrefs_summary.tsv', directory=directory)


def _write_tsv(df: pd.DataFrame, name: str, *, directory: Optional[str] = None) -> None:
    df.to_csv(os.path.join(directory or DATABASE_DIRECTORY, name), sep='\t', index=False)


if __name__ == '__main__':
    database()
