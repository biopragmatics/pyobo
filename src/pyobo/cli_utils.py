# -*- coding: utf-8 -*-

"""Utilities for the CLI."""

import logging

import click
import pandas as pd

from .constants import DATABASE_DIRECTORY

__all__ = [
    'verbose_option',
    'directory_option',
    'echo_df',
]

logger = logging.getLogger(__name__)

LOG_FMT = '%(asctime)s %(levelname)-8s %(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'


def _debug_callback(_ctx, _param, value):
    if not value:
        logging.basicConfig(level=logging.WARNING, format=LOG_FMT, datefmt=LOG_DATEFMT)
    elif value == 1:
        logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DATEFMT)
    else:
        logging.basicConfig(level=logging.DEBUG, format=LOG_FMT, datefmt=LOG_DATEFMT)


verbose_option = click.option(
    '-v', '--verbose',
    count=True,
    callback=_debug_callback,
    expose_value=False,
)

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
