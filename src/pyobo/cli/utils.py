"""Utilities for the CLI."""

import datetime
import pathlib
from collections.abc import Callable
from typing import TypeVar

import click
import pandas as pd

from ..constants import DATABASE_DIRECTORY

__all__ = [
    "Clickable",
    "directory_option",
    "echo_df",
    "force_option",
    "force_process_option",
    "prefix_argument",
    "strict_option",
    "zenodo_option",
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
strict_option = click.option(
    "--strict/--no-strict",
    default=False,
    show_default=True,
    help="Turn on or off failure on unparsable CURIEs",
)
prefix_argument = click.argument("prefix")
force_option = click.option(
    "-f", "--force", is_flag=True, help="Force re-downloading and re-processing"
)
version_option = click.option(
    "--version",
    help="Explicit version of the data. If not given, the most recent will be looked up.",
)
force_process_option = click.option(
    "--force-process", is_flag=True, help="Force re-processing, but not necessarily re-downloading"
)
Clickable = TypeVar("Clickable", bound=Callable)
