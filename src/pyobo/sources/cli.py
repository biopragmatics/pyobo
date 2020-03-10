# -*- coding: utf-8 -*-

"""Run the exporter."""

import click

from .utils import get_converted_obos

__all__ = ['main']


@click.command()
def main():
    """Run the exporter."""
    for obo in get_converted_obos():
        obo.write_default()


if __name__ == '__main__':
    main()
