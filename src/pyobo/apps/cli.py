# -*- coding: utf-8 -*-

"""CLI for PyOBO apps."""

import click

from .gilda.cli import main as gilda_main
from .mapper.cli import main as mapper_main

__all__ = [
    "main",
]


@click.group(name="apps")
def main():
    """Apps."""


main.add_command(gilda_main)
main.add_command(mapper_main)

if __name__ == "__main__":
    main()
