# -*- coding: utf-8 -*-

"""CLI for PyOBO's Mapping Service.

Run with ``python -m pyobo.apps.mapper``.
"""

import click
from more_click import (
    host_option,
    port_option,
    run_app,
    verbose_option,
    with_gunicorn_option,
)

__all__ = [
    "main",
]


@click.command(name="mapper")
@click.option("-x", "--mappings-file")
@port_option
@host_option
@with_gunicorn_option
@verbose_option
def main(mappings_file, host: str, port: str, with_gunicorn: bool):
    """Run the mappings app."""
    from .mapper import get_app

    app = get_app(mappings_file)
    run_app(app=app, host=host, port=port, with_gunicorn=with_gunicorn)


if __name__ == "__main__":
    main()
