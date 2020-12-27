# -*- coding: utf-8 -*-

"""Utilities for the CLI."""

import click
import pandas as pd
from more_click import verbose_option

from .constants import DATABASE_DIRECTORY

__all__ = [
    'verbose_option',
    'directory_option',
    'echo_df',
]

directory_option = click.option(
    '-d', '--directory',
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
    default=DATABASE_DIRECTORY,
    show_default=True,
)


def echo_df(df: pd.DataFrame) -> None:
    """Echo a dataframe via the pager."""
    click.echo_via_pager('\n'.join(
        '\t'.join(row)
        for row in df.values
    ))
