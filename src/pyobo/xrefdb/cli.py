# -*- coding: utf-8 -*-

"""Extract *all* xrefs from OBO documents available."""

import gzip
import os
from collections import Counter

import click
import pandas as pd

from .xrefs_pipeline import _iter_ooh_na_na, get_xref_df, summarize_xref_df
from ..cli_utils import verbose_option
from ..identifier_utils import UNHANDLED_NAMESPACES

directory_option = click.option(
    '-d', '--directory',
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
    default=os.getcwd(),
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
    _write_tsv(xrefs_df, f'inspector_javerts_xrefs.tsv.gz')

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), f'inspector_javerts_xrefs_sample.tsv')

    # Export a summary dataframe
    summary_df = summarize_xref_df(xrefs_df)
    _write_tsv(summary_df, 'inspector_javerts_xref_summary.tsv')

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

    path = os.path.join(directory, 'ooh_na_na.tsv.gz')
    with gzip.open(path, mode='wt') as gzipped_file:
        print('prefix', 'identifier', 'name', sep='\t', file=gzipped_file)
        for prefix, identifier, name in _iter_ooh_na_na():
            c[prefix] += 1
            print(prefix, identifier, name, sep='\t', file=gzipped_file)

    path = os.path.join(directory, 'summary.tsv')
    with open(path, 'w') as file:
        for k, v in c.most_common():
            print(k, v, sep='\t', file=file)


if __name__ == '__main__':
    output()
