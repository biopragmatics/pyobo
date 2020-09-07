# -*- coding: utf-8 -*-

"""CLI for PyOBO Database Generation.

Run with ``obo database <subcommand>``.
"""

import os

import click
import pandas as pd

from .cli_utils import directory_option, verbose_option
from .constants import PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX
from .getters import db_output_helper
from .identifier_utils import hash_curie
from .xrefdb.xrefs_pipeline import (
    Canonicalizer, _iter_alts, _iter_ooh_na_na, _iter_synonyms, get_xref_df,
    summarize_xref_df,
)


@click.group()
def database():
    """Build the PyOBO Database."""


@database.command()
@directory_option
@verbose_option
@click.pass_context
def build(ctx: click.Context, directory: str):
    """Build all databases."""
    ctx.invoke(alts)
    ctx.invoke(synonyms)
    ctx.invoke(xrefs)
    ctx.invoke(names)


@database.command()
@directory_option
@verbose_option
def names(directory: str):
    """Make the prefix-identifier-name dump."""
    db_output_helper(directory, _iter_ooh_na_na, 'names', ('prefix', 'identifier', 'name'))


@database.command()
@directory_option
@verbose_option
def alts(directory: str):
    """Make the prefix-alt-id dump."""
    db_output_helper(directory, _iter_alts, 'alts', ('prefix', 'identifier', 'alt'))


@database.command()
@directory_option
@verbose_option
def synonyms(directory: str):
    """Make the prefix-identifier-synonym dump."""
    db_output_helper(directory, _iter_synonyms, 'synonyms', ('prefix', 'identifier', 'synonym'))


@database.command()
@directory_option
@verbose_option
def xrefs(directory: str):  # noqa: D202
    """Make the prefix-identifier-xref dump."""

    def _write_tsv(df: pd.DataFrame, name: str) -> None:
        df.to_csv(os.path.join(directory, name), sep='\t', index=False)

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


@database.command()
@verbose_option
@click.option('-f', '--file', type=click.File('w'))
def remapping(file):
    """Make a canonical remapping."""
    canonicalizer = Canonicalizer.get_default()
    print('input', 'canonical', sep='\t', file=file)
    for source, target in canonicalizer.iterate_flat_mapping():
        print(source, target, sep='\t', file=file)


if __name__ == '__main__':
    database()
