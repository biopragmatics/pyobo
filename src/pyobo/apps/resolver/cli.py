# -*- coding: utf-8 -*-

"""PyOBO's Resolution Service.

Run with ``python -m pyobo.apps.resolver``
"""

import logging
import sys
from typing import Optional

import click
from more_click import host_option, port_option, run_app, verbose_option, with_gunicorn_option

__all__ = [
    "main",
]


@click.command(name="resolver")
@port_option
@host_option
@click.option("--name-data", help="local 3-column gzipped TSV as database")
@click.option("--alts-data", help="local 3-column gzipped TSV as database")
@click.option("--defs-data", help="local 3-column gzipped TSV as database")
@click.option(
    "--sql",
    is_flag=True,
    help="Use a sql database backend. If not used, defaults to in memory dictionaries",
)
@click.option("--sql-uri", help="SQL URI string if using --sql. ")
@click.option("--sql-refs-table", help="use preloaded SQL database as backend")
@click.option("--sql-alts-table", help="use preloaded SQL database as backend")
@click.option("--sql-defs-table", help="use preloaded SQL database as backend")
@click.option("--lazy", is_flag=True, help="do no load full cache into memory automatically")
@click.option("--test", is_flag=True, help="run in test mode with only a few datasets")
@click.option("--workers", type=int, help="number of workers to use in --gunicorn mode")
@with_gunicorn_option
@verbose_option
def main(
    port: str,
    host: str,
    sql: bool,
    sql_uri: Optional[str],
    sql_refs_table: Optional[str],
    sql_alts_table: Optional[str],
    sql_defs_table: Optional[str],
    name_data: Optional[str],
    alts_data: Optional[str],
    defs_data: Optional[str],
    test: bool,
    with_gunicorn: bool,
    lazy: bool,
    workers: int,
):
    """Run the resolver app."""
    if test:
        if lazy:
            click.secho("Can not run in --test and --lazy mode at the same time", fg="red")
            sys.exit(0)
        if sql:
            click.secho("Can not run in --test and --sql mode at the same time", fg="red")
            sys.exit(0)

    from .resolver import get_app

    if test:
        from pyobo import get_id_name_mapping, get_alts_to_id, get_id_definition_mapping
        import pandas as pd

        prefixes = ["hgnc", "chebi", "doid", "go", "uniprot"]
        name_data = pd.DataFrame(
            [
                (prefix, identifier, name)
                for prefix in prefixes
                for identifier, name in get_id_name_mapping(prefix).items()
            ],
            columns=["prefix", "identifier", "name"],
        )
        click.echo(f"prepared {len(name_data):,} test names from {prefixes}")
        alts_data = pd.DataFrame(
            [
                (prefix, alt, identifier)
                for prefix in prefixes
                for alt, identifier in get_alts_to_id(prefix).items()
            ],
            columns=["prefix", "alt", "identifier"],
        )
        click.echo(f"prepared {len(alts_data):,} test alts from {prefixes}")
        defs_data = pd.DataFrame(
            [
                (prefix, identifier, definition)
                for prefix in prefixes
                for identifier, definition in get_id_definition_mapping(prefix).items()
            ],
            columns=["prefix", "identifier", "definition"],
        )
        click.echo(f"prepared {len(defs_data):,} test defs from {prefixes}")

    app = get_app(
        name_data=name_data,
        alts_data=alts_data,
        defs_data=defs_data,
        lazy=lazy,
        sql=sql,
        uri=sql_uri,
        refs_table=sql_refs_table,
        alts_table=sql_alts_table,
        defs_table=sql_defs_table,
    )

    from pyobo.constants import PYOBO_MODULE

    log_path = PYOBO_MODULE.join("biolookup", name="log.txt")
    # see logging cookbook https://docs.python.org/3/howto/logging-cookbook.html
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)

    from . import backends, resolver

    logging.getLogger("werkzeug").addHandler(fh)
    backends.logger.setLevel(logging.DEBUG)
    backends.logger.addHandler(fh)
    resolver.logger.setLevel(logging.DEBUG)
    resolver.logger.addHandler(fh)

    run_app(app=app, host=host, port=port, with_gunicorn=with_gunicorn, workers=workers)


if __name__ == "__main__":
    main()
