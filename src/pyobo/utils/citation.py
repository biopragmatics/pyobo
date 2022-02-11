# -*- coding: utf-8 -*-

"""Normalization of citation URLs."""

import warnings
from typing import Tuple, Union

import citation_url
import click

__all__ = [
    "normalize_citation",
]


def normalize_citation(line: str) -> Union[Tuple[str, str], Tuple[None, str]]:
    """Normalize a citation string that might be a crazy URL from a publisher."""
    warnings.warn("this function has been externalized to :func:`citation_url.parse`")
    return citation_url.parse(line)


@click.command()
@click.option("-f", "--file", type=click.File())
def main(file):
    """Normalize a file with random citations."""
    for line in file:
        line = line.strip()
        prefix, identifier = normalize_citation(line)
        if not prefix or not identifier:
            click.echo(f"unnormalized: {line}")
        else:
            click.echo(f"{prefix}\t{identifier}")


if __name__ == "__main__":
    main()
