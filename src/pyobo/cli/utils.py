# -*- coding: utf-8 -*-

"""Utilities for the CLI."""

import click
import pandas as pd

__all__ = [
    'echo_df',
    'force_option',
    'prefix_argument',
]

prefix_argument = click.argument('prefix')
force_option = click.option('-f', '--force', is_flag=True)


def echo_df(df: pd.DataFrame) -> None:
    """Echo a dataframe via the pager."""
    click.echo_via_pager('\n'.join(
        '\t'.join(row)
        for row in df.values
    ))
