# -*- coding: utf-8 -*-

"""CLI for PyOBO database."""

import click

from pyobo.cli_utils import verbose_option

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
@verbose_option
def load():
    """Load the SQL database."""
    from .sql.loader import load as _load
    whitelist = {
        'hp', 'go', 'hgnc', 'efo', 'mesh', 'rgd', 'mgi', 'chebi', 'drugbank', 'interpro',
        'mirbase', 'mirbase.family', 'npass', 'ncbitaxon',
    }
    _load()


@sql.command()
@verbose_option
def web():
    """Run the flask-admin frontend."""
    from .sql.wsgi import app
    app.run()


if __name__ == '__main__':
    main()
