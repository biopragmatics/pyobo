# -*- coding: utf-8 -*-

"""CLI for PyOBO database."""

import click

__all__ = [
    'main',
]


@click.group()
def main():
    """CLI for PyOBO database."""


@main.group()
def sql():
    """CLI for SQL database."""


@sql.command()
def load():
    """Load the SQL database."""
    from .sql.loader import load as _load
    _load(whitelist={'mesh', 'hpo', 'hp', 'efo', 'snomedct'})


@sql.command()
def web():
    """Run the flask-admin frontend."""
    from .sql.frontend import app
    app.run()


if __name__ == '__main__':
    main()
