# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service.

Run with ``python -m pyobo.apps.resolver``
"""

import sys
from typing import Optional

import click
from more_click import host_option, port_option, run_app, verbose_option, with_gunicorn_option

__all__ = [
    'main',
]


@click.command(name='resolver')
@port_option
@host_option
@click.option('--data', help='local 3-column gzipped TSV as database')
@click.option('--sql', is_flag=True)
@click.option('--sql-uri')
@click.option('--sql-refs-table', help='use preloaded SQL database as backend')
@click.option('--sql-alts-table', help='use preloaded SQL database as backend')
@click.option('--sql-defs-table', help='use preloaded SQL database as backend')
@click.option('--lazy', is_flag=True, help='do no load full cache into memory automatically')
@click.option('--test', is_flag=True, help='run in test mode with only a few datasets')
@click.option('--workers', type=int, help='number of workers to use in --gunicorn mode')
@with_gunicorn_option
@verbose_option
def main(
    port: str,
    host: str,
    sql: bool,
    sql_uri: str,
    sql_refs_table: str,
    sql_alts_table: str,
    sql_defs_table: str,
    data: Optional[str],
    test: bool,
    with_gunicorn: bool,
    lazy: bool,
    workers: int,
):
    """Run the resolver app."""
    if test and lazy:
        click.secho('Can not run in --test and --lazy mode at the same time', fg='red')
        sys.exit(0)

    from .resolver import get_app

    if test:
        from pyobo import get_id_name_mapping
        import pandas as pd
        data = [
            (prefix, identifier, name)
            for prefix in ['hgnc', 'chebi', 'doid', 'go']
            for identifier, name in get_id_name_mapping(prefix).items()
        ]
        data = pd.DataFrame(data, columns=['prefix', 'identifier', 'name'])

    app = get_app(
        data,
        lazy=lazy,
        sql=sql,
        uri=sql_uri,
        refs_table=sql_refs_table,
        alts_table=sql_alts_table,
        defs_table=sql_defs_table,
    )
    run_app(app=app, host=host, port=port, with_gunicorn=with_gunicorn, workers=workers)


if __name__ == '__main__':
    main()
