# -*- coding: utf-8 -*-

"""Utilities for the CLI."""

import click
import pandas as pd
from more_click import verbose_option

__all__ = [
    'verbose_option',
    'echo_df',
]


def echo_df(df: pd.DataFrame) -> None:
    """Echo a dataframe via the pager."""
    click.echo_via_pager('\n'.join(
        '\t'.join(row)
        for row in df.values
    ))
