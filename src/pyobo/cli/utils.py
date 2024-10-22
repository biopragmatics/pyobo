"""Utilities for the CLI."""

import datetime
import pathlib

import click
import pandas as pd

from ..constants import DATABASE_DIRECTORY

__all__ = [
    "echo_df",
    "directory_option",
    "zenodo_option",
    "force_option",
    "prefix_argument",
    "no_strict_option",
]


def echo_df(df: pd.DataFrame) -> None:
    """Echo a dataframe via the pager."""
    click.echo_via_pager("\n".join("\t".join(row) for row in df.values))


def get_default_directory() -> pathlib.Path:
    """Get the default database build directory."""
    rv = DATABASE_DIRECTORY / datetime.datetime.today().strftime("%Y-%m-%d")
    rv.mkdir(exist_ok=True, parents=True)
    return rv


directory_option = click.option(
    "--directory",
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
    default=get_default_directory,
    help=f"Build location. Defaults to {DATABASE_DIRECTORY}/<today>",
)
zenodo_option = click.option("--zenodo", is_flag=True, help="Automatically upload to zenodo")
no_strict_option = click.option(
    "-x", "--no-strict", is_flag=True, help="Turn off failure on bad CURIEs"
)
prefix_argument = click.argument("prefix")
force_option = click.option("-f", "--force", is_flag=True)
version_option = click.option(
    "--version",
    help="Explicit version of the data. If not given, the most recent will be looked up.",
)
