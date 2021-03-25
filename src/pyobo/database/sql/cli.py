# -*- coding: utf-8 -*-

"""CLI for PyOBO SQL database."""

import click
from more_click import make_web_command, verbose_option

from pyobo.constants import ALTS_TABLE_NAME, REFS_TABLE_NAME, get_sqlalchemy_uri
from pyobo.resource_utils import ensure_alts, ensure_ooh_na_na


@click.group(name='sql')
def database_sql():
    """PyOBO SQL Database."""  # noqa:D403


@database_sql.command()
@click.option('--uri', default=get_sqlalchemy_uri, help='The database URL.', show_default=True)
@click.option('--refs-table', default=REFS_TABLE_NAME, show_default=True)
@click.option('--refs-path', default=ensure_ooh_na_na, show_default=True, help='By default, load from Zenodo')
@click.option('--alts-table', default=ALTS_TABLE_NAME, show_default=True)
@click.option('--alts-path', default=ensure_alts, show_default=True, help='By default, load from Zenodo')
@click.option('--test', is_flag=True, help='Test run with a small test subset')
@verbose_option
def load(uri: str, refs_table: str, refs_path: str, alts_table: str, alts_path: str, test: bool):
    """Load the SQL database."""
    from .loader import load as _load
    _load(uri=uri, refs_table=refs_table, refs_path=refs_path, alts_table=alts_table, alts_path=alts_path, test=test)


make_web_command('pyobo.database.sql.wsgi:app', group=database_sql)

if __name__ == '__main__':
    database_sql()
