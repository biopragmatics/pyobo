# -*- coding: utf-8 -*-

"""CLI for PyOBO."""

import click

from .mappings import get_all_xrefs, get_id_name_mapping, get_synonyms, get_xrefs

__all__ = ['main']


@click.group()
def main():
    """CLI for PyOBO."""


prefix_argument = click.argument('prefix')


@main.command()
@prefix_argument
@click.option('--target')
def xrefs(prefix: str, target: str):
    """Page through xrefs for the given namespace to the second given namespace."""
    if target:
        click.echo_via_pager('\n'.join(
            f'{identifier}\t{_xref}'
            for identifier, _xrefs in get_xrefs(prefix, target).items()
            for _xref in _xrefs
        ))
    else:
        click.echo_via_pager('\n'.join(
            '\t'.join(row)
            for row in get_all_xrefs(prefix).values
        ))


@main.command()
@prefix_argument
def names(prefix: str):
    """Page through the identifiers and names of entities in the given namespace."""
    click.echo_via_pager('\n'.join(
        '\t'.join(item)
        for item in get_id_name_mapping(prefix).items()
    ))


@main.command()
@prefix_argument
def synonyms(prefix: str):
    """Page through the synonyms for entities in the given namespace."""
    click.echo_via_pager('\n'.join(
        f'{identifier}\t{_synonym}'
        for identifier, _synonyms in get_synonyms(prefix).items()
        for _synonym in _synonyms
    ))


if __name__ == '__main__':
    main()
