# -*- coding: utf-8 -*-

"""CLI for PyOBO."""

import logging
import os

import click

from .cli_utils import echo_df, verbose_option
from .constants import PYOBO_HOME
from .extract import (
    get_filtered_xrefs, get_id_name_mapping, get_id_synonyms_mapping, get_properties_df,
    get_relations_df, get_xrefs_df,
)
from .sources import iter_converted_obos
from .xrefdb.cli import cache_xrefs

__all__ = ['main']

logger = logging.getLogger(__name__)


@click.group()
def main():
    """CLI for PyOBO."""


prefix_argument = click.argument('prefix')


@main.command()
@prefix_argument
@click.option('--target')
@verbose_option
def xrefs(prefix: str, target: str):
    """Page through xrefs for the given namespace to the second given namespace."""
    if target:
        filtered_xrefs = get_filtered_xrefs(prefix, target)
        click.echo_via_pager('\n'.join(
            f'{identifier}\t{_xref}'
            for identifier, _xrefs in filtered_xrefs.items()
            for _xref in _xrefs
        ))
    else:
        all_xrefs_df = get_xrefs_df(prefix)
        echo_df(all_xrefs_df)


@main.command()
@prefix_argument
@verbose_option
def names(prefix: str):
    """Page through the identifiers and names of entities in the given namespace."""
    id_to_name = get_id_name_mapping(prefix)
    click.echo_via_pager('\n'.join(
        '\t'.join(item)
        for item in id_to_name.items()
    ))


@main.command()
@prefix_argument
@verbose_option
def synonyms(prefix: str):
    """Page through the synonyms for entities in the given namespace."""
    id_to_synonyms = get_id_synonyms_mapping(prefix)
    click.echo_via_pager('\n'.join(
        f'{identifier}\t{_synonym}'
        for identifier, _synonyms in id_to_synonyms.items()
        for _synonym in _synonyms
    ))


@main.command()
@prefix_argument
@verbose_option
def relations(prefix: str):
    """Page through the relations for entities in the given namespace."""
    relations_df = get_relations_df(prefix)
    echo_df(relations_df)


@main.command()
@prefix_argument
@verbose_option
def properties(prefix: str):
    """Page through the properties for entities in the given namespace."""
    properties_df = get_properties_df(prefix)
    echo_df(properties_df)


@main.command()
@verbose_option
def cache():
    """Cache all resources."""
    for obo in iter_converted_obos():
        click.secho(f'Caching {obo.ontology}', bold=True, fg='green')
        obo.write_default()


@main.command()
@click.option('--remove-obo', is_flag=True)
def clean(remove_obo: bool):
    """Delete all cached files."""
    suffixes = [
        '_mappings.tsv', '.mapping.tsv', '_synonyms.tsv',
        '.obo.pickle', '.obo.json.gz', '.owl',
    ]
    if remove_obo:
        suffixes.append('.obo')
    for directory in os.listdir(PYOBO_HOME):
        d = os.path.join(PYOBO_HOME, directory)
        if not os.path.isdir(d):
            continue
        entities = list(os.listdir(d))
        if not entities:
            os.rmdir(d)
        obo_pickle = os.path.join(d, f'{directory}.obo.pickle')
        if os.path.exists(obo_pickle):
            os.remove(obo_pickle)
        for f in entities:
            if any(f.endswith(suffix) for suffix in suffixes):
                os.remove(os.path.join(d, f))


main.add_command(cache_xrefs)

if __name__ == '__main__':
    main()
