# -*- coding: utf-8 -*-

"""CLI for PyOBO Database Generation.

Run with ``obo database <subcommand>``.
"""

import click
import pandas as pd

from .cli_utils import verbose_option
from .constants import DATABASE_DIRECTORY, PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX
from .getters import db_output_helper
from .identifier_utils import hash_curie
from .xrefdb.xrefs_pipeline import _iter_alts, _iter_ooh_na_na, _iter_synonyms, get_xref_df, summarize_xref_df


@click.group()
def database():
    """Build the PyOBO Database."""


@database.command()
@verbose_option
@click.pass_context
def build(ctx: click.Context):
    """Build all databases."""
    click.secho('Alternate Identifiers', fg='cyan', bold=True)
    ctx.invoke(alts)
    click.secho('Synonyms', fg='cyan', bold=True)
    ctx.invoke(synonyms)
    click.secho('Xrefs', fg='cyan', bold=True)
    ctx.invoke(xrefs)
    click.secho('Names', fg='cyan', bold=True)
    ctx.invoke(names)


@database.command()
@verbose_option
def names():
    """Make the prefix-identifier-name dump."""
    db_output_helper(_iter_ooh_na_na, 'names', ('prefix', 'identifier', 'name'))


@database.command()
@verbose_option
def alts():
    """Make the prefix-alt-id dump."""
    db_output_helper(_iter_alts, 'alts', ('prefix', 'identifier', 'alt'))


@database.command()
@verbose_option
def synonyms():
    """Make the prefix-identifier-synonym dump."""
    db_output_helper(_iter_synonyms, 'synonyms', ('prefix', 'identifier', 'synonym'))


@database.command()
@verbose_option
def xrefs():  # noqa: D202
    """Make the prefix-identifier-xref dump."""
    xrefs_df = get_xref_df()

    # Export all xrefs
    _write_tsv(xrefs_df, 'xrefs.tsv.gz')

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), 'xrefs_sample.tsv')

    md5_df = pd.DataFrame({
        'md5': [hash_curie(p, i) for p, i in xrefs_df[[SOURCE_PREFIX, SOURCE_ID]].values],
        'xref_md5': [hash_curie(p, i) for p, i in xrefs_df[[TARGET_PREFIX, TARGET_ID]].values],
        'source': xrefs_df[PROVENANCE],
    })
    _write_tsv(md5_df, 'xrefs_md5.tsv.gz')
    _write_tsv(md5_df.head(), 'xrefs_md5_sample.tsv')

    # Export a summary dataframe
    summary_df = summarize_xref_df(xrefs_df)
    _write_tsv(summary_df, 'xrefs_summary.tsv')


def _write_tsv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(DATABASE_DIRECTORY / name, sep='\t', index=False)


if __name__ == '__main__':
    database()
