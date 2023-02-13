# -*- coding: utf-8 -*-

"""Normalization of citation URLs."""

import citation_url
import click


@click.command()
@click.option("-f", "--file", type=click.File())
def main(file):
    """Normalize a file with random citations."""
    for line in file:
        line = line.strip()
        prefix, identifier = citation_url.parse(line)
        if not prefix or not identifier:
            click.echo(f"unnormalized: {line}")
        else:
            click.echo(f"{prefix}\t{identifier}")


if __name__ == "__main__":
    main()
