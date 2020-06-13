# -*- coding: utf-8 -*-

"""Extract *all* xrefs from OBO documents available."""

import gzip
import os
from collections import Counter

import click
import pandas as pd

from .xrefs_pipeline import Canonicalizer, _iter_ooh_na_na, _iter_synonyms, get_xref_df, summarize_xref_df
from ..cli_utils import verbose_option
from ..constants import PYOBO_HOME
from ..identifier_utils import UNHANDLED_NAMESPACES

directory_option = click.option(
    '-d', '--directory',
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
    default=PYOBO_HOME,
)


@click.group()
def output():
    """Output all OBO documents available."""


@output.command()
@directory_option
@verbose_option
def javerts_xrefs(directory: str):  # noqa: D202
    """Make the xref dump."""

    def _write_tsv(df: pd.DataFrame, name: str) -> None:
        df.to_csv(os.path.join(directory, name), sep='\t', index=False)

    xrefs_df = get_xref_df()

    # Export all xrefs
    _write_tsv(xrefs_df, 'inspector_javerts_xrefs.tsv.gz')

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), 'inspector_javerts_xrefs_sample.tsv')

    # Export a summary dataframe
    summary_df = summarize_xref_df(xrefs_df)
    _write_tsv(summary_df, 'inspector_javerts_xrefs_summary.tsv')

    # Export the namespaces that haven't been handled yet
    unmapped_path = os.path.join(directory, 'inspector_javerts_unmapped_xrefs.tsv')
    with open(unmapped_path, 'w') as file:
        for namespace, items in sorted(UNHANDLED_NAMESPACES.items()):
            for curie, xref in items:
                print(curie, namespace, xref, file=file, sep='\t')


@output.command()
@directory_option
@verbose_option
def ooh_na_na(directory: str):
    """Make the prefix-identifier-name dump."""
    c = Counter()

    db_path = os.path.join(directory, 'ooh_na_na.tsv.gz')
    click.echo(f'Writing Ooh-Na-Na to {db_path}')
    with gzip.open(db_path, mode='wt') as gzipped_file:
        print('prefix', 'identifier', 'name', sep='\t', file=gzipped_file)
        for prefix, identifier, name in _iter_ooh_na_na():
            c[prefix] += 1
            print(prefix, identifier, name, sep='\t', file=gzipped_file)

    summary_path = os.path.join(directory, 'ooh_na_na_summary.tsv')
    click.echo(f'Writing Ooh-Na-Na summary to {summary_path}')
    with open(summary_path, 'w') as file:
        for k, v in c.most_common():
            print(k, v, sep='\t', file=file)


@output.command()
@directory_option
@verbose_option
def synonymsdb(directory: str):
    """Make the prefix-identifier-synonym dump."""
    c = Counter()
    db_path = os.path.join(directory, 'synonymdb.tsv.gz')
    click.echo(f'Writing SynonymDB to {db_path}')
    with gzip.open(db_path, mode='wt') as gzipped_file:
        print('prefix', 'identifier', 'name', sep='\t', file=gzipped_file)
        for prefix, identifier, name in _iter_synonyms():
            c[prefix] += 1
            print(prefix, identifier, name, sep='\t', file=gzipped_file)
    summary_path = os.path.join(directory, 'synonym_summary.tsv')
    click.echo(f'Writing SynonymDB summary to {summary_path}')
    with open(summary_path, 'w') as file:
        for k, v in c.most_common():
            print(k, v, sep='\t', file=file)


@output.command()
@verbose_option
@click.option('-f', '--file', type=click.File('w'))
def javerts_remapping(file):
    """Make a canonical remapping."""
    canonicalizer = Canonicalizer.get_default()
    print('input', 'canonical', sep='\t', file=file)
    for source, target in canonicalizer.iterate_flat_mapping():
        print(source, target, sep='\t', file=file)


if __name__ == '__main__':
    output()
