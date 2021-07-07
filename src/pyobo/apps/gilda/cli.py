# -*- coding: utf-8 -*-

"""CLI for PyOBO's Gilda Service."""

import click
from more_click import (
    host_option,
    port_option,
    run_app,
    verbose_option,
    with_gunicorn_option,
    workers_option,
)

__all__ = [
    "main",
]


@click.command(name="gilda")
@click.argument("prefix", nargs=-1)
@verbose_option
@host_option
@workers_option
@port_option
@with_gunicorn_option
def main(prefix: str, host: str, port: str, with_gunicorn: bool, workers: int):
    """Run the Gilda service for this database."""
    from .app import get_app

    app = get_app(prefix)
    run_app(app, host=host, port=port, with_gunicorn=with_gunicorn, workers=workers)


if __name__ == "__main__":
    main()
