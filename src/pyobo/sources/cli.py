# -*- coding: utf-8 -*-

"""Run the exporter."""

import os
from importlib import import_module

import click

__all__ = ['main']

HERE = os.path.abspath(os.path.dirname(__file__))


@click.command()
def main():
    """Run the exporter."""
    for fname in os.listdir(HERE):
        if fname in {'__init__.py', '__main__.py', 'cli.py', 'utils.py'} or not os.path.isfile(fname):
            continue
        prefix = fname[:-len('.py')]
        click.echo(f'Importing {prefix}')
        import_module(prefix).get_obo().write_default()


if __name__ == '__main__':
    main()
