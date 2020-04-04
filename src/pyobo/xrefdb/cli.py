# -*- coding: utf-8 -*-

"""Extract *all* xrefs from OBO documents available."""

import os

import click
import pandas as pd

from .xrefs_pipeline import get_xref_df
from ..cli_utils import verbose_option
from ..identifier_utils import UNHANDLED_NAMESPACES


@click.group()
def output():
    """Output all OBO documents available."""


@output.command()
@click.option('--directory', type=click.Path(dir_okay=True, file_okay=False, exists=True), default=os.getcwd())
@verbose_option
def cache_xrefs(directory):  # noqa: D202
    """Output the mappings."""

    def _write_tsv(df: pd.DataFrame, name: str) -> None:
        df.to_csv(os.path.join(directory, name), sep='\t', index=False)

    xrefs_df = get_xref_df()

    # Export all xrefs
    _write_tsv(xrefs_df, f'xrefs.tsv')
    _write_tsv(xrefs_df, f'xrefs.tsv.gz')

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), f'xrefs_sample.tsv')

    # Export a summary dataframe
    summary_df = xrefs_df.groupby(['source', 'target_ns'])['source_ns'].count().reset_index()
    summary_df = summary_df.sort_values(['source_ns'], ascending=False)
    _write_tsv(summary_df, 'summary.tsv')

    # Export the namespaces that haven't been handled yet
    unmapped_path = os.path.join(directory, 'unmapped.tsv')
    with open(unmapped_path, 'w') as file:
        for namespace, items in sorted(UNHANDLED_NAMESPACES.items()):
            for curie, xref in items:
                print(curie, namespace, xref, file=file, sep='\t')


if __name__ == '__main__':
    output()
