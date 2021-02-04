# -*- coding: utf-8 -*-

"""CLI for PyOBO."""

import logging
import os
import sys
from operator import itemgetter
from typing import Optional

import click
import humanize
from more_click import verbose_option
from tabulate import tabulate

from . import aws, cli_database
from .cli_utils import echo_df
from .constants import RAW_DIRECTORY
from .extract import (
    get_ancestors, get_descendants, get_filtered_properties_df, get_filtered_relations_df, get_filtered_xrefs,
    get_hierarchy, get_id_name_mapping, get_id_synonyms_mapping, get_id_to_alts, get_name, get_name_by_curie,
    get_properties_df, get_relations_df, get_typedef_id_name_mapping, get_xrefs_df, iter_cached_obo,
)
from .identifier_utils import normalize_curie, normalize_prefix
from .sources import has_nomenclature_plugin, iter_nomenclature_plugins
from .xrefdb.canonicalizer import Canonicalizer, get_priority_curie, remap_file_stream
from .xrefdb.priority import DEFAULT_PRIORITY_LIST

__all__ = ['main']

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main():
    """CLI for PyOBO."""


prefix_argument = click.argument('prefix')
force_option = click.option('-f', '--force', is_flag=True)


@main.command()
@prefix_argument
@click.option('-t', '--target')
@verbose_option
@force_option
def xrefs(prefix: str, target: str, force: bool):
    """Page through xrefs for the given namespace to the second given namespace."""
    if target:
        filtered_xrefs = get_filtered_xrefs(prefix, target, force=force)
        click.echo_via_pager('\n'.join(
            f'{identifier}\t{_xref}'
            for identifier, _xref in filtered_xrefs.items()
        ))
    else:
        all_xrefs_df = get_xrefs_df(prefix)
        echo_df(all_xrefs_df)


@main.command()
@prefix_argument
@verbose_option
@force_option
def names(prefix: str, force: bool):
    """Page through the identifiers and names of entities in the given namespace."""
    id_to_name = get_id_name_mapping(prefix, force=force)
    _help_page_mapping(id_to_name)


@main.command()
@prefix_argument
@verbose_option
@force_option
def typedefs(prefix: str, force: bool):
    """Page through the identifiers and names of typedefs in the given namespace."""
    id_to_name = get_typedef_id_name_mapping(prefix, force=force)
    _help_page_mapping(id_to_name)


def _help_page_mapping(id_to_name):
    click.echo_via_pager('\n'.join(
        '\t'.join(item)
        for item in id_to_name.items()
    ))


@main.command()
@prefix_argument
@verbose_option
@force_option
def synonyms(prefix: str, force: bool):
    """Page through the synonyms for entities in the given namespace."""
    if ':' in prefix:
        prefix, identifier = normalize_curie(prefix)
        name = get_name(prefix, identifier)
        id_to_synonyms = get_id_synonyms_mapping(prefix, force=force)
        click.echo(f'Synonyms for {prefix}:{identifier} ! {name}')
        for synonym in id_to_synonyms.get(identifier, []):
            click.echo(synonym)
    else:  # it's a prefix
        id_to_synonyms = get_id_synonyms_mapping(prefix, force=force)
        click.echo_via_pager('\n'.join(
            f'{identifier}\t{_synonym}'
            for identifier, _synonyms in id_to_synonyms.items()
            for _synonym in _synonyms
        ))


@main.command()
@prefix_argument
@click.option('--relation', help='CURIE for the relationship or just the ID if local to the ontology')
@click.option('--target', help='Prefix for the target')
@verbose_option
@force_option
def relations(prefix: str, relation: str, target: str, force: bool):
    """Page through the relations for entities in the given namespace."""
    if relation is None:
        relations_df = get_relations_df(prefix, force=force)
    else:
        curie = normalize_curie(relation)
        if curie[1] is None:  # that's the identifier
            click.secho(f'not valid curie, assuming local to {prefix}', fg='yellow')
            curie = prefix, relation

        if target is None:
            relations_df = get_filtered_relations_df(prefix, relation=curie, force=force)
        else:
            raise NotImplementedError(f'can not filter by target prefix {target}')

    echo_df(relations_df)


@main.command()
@prefix_argument
@click.option('--include-part-of', is_flag=True)
@click.option('--include-has-member', is_flag=True)
@verbose_option
@force_option
def hierarchy(prefix: str, include_part_of: bool, include_has_member: bool, force: bool):
    """Page through the hierarchy for entities in the namespace."""
    h = get_hierarchy(prefix, include_part_of=include_part_of, include_has_member=include_has_member)
    click.echo_via_pager('\n'.join(
        '\t'.join(row)
        for row in h.edges()
    ))


@main.command()
@prefix_argument
@click.argument('identifier')
@verbose_option
@force_option
def ancestors(prefix: str, identifier: str, force: bool):
    """Look up ancestors."""
    curies = get_ancestors(prefix=prefix, identifier=identifier, force=force)
    for curie in curies:
        click.echo(f'{curie}\t{get_name_by_curie(curie)}')


@main.command()
@prefix_argument
@click.argument('identifier')
@verbose_option
@force_option
def descendants(prefix: str, identifier: str, force: bool):
    """Look up descendants."""
    curies = get_descendants(prefix=prefix, identifier=identifier, force=force)
    for curie in curies:
        click.echo(f'{curie}\t{get_name_by_curie(curie)}')


@main.command()
@prefix_argument
@click.option('-k', '--key')
@verbose_option
@force_option
def properties(prefix: str, key: Optional[str], force: bool):
    """Page through the properties for entities in the given namespace."""
    if key is None:
        properties_df = get_properties_df(prefix, force=force)
    else:
        properties_df = get_filtered_properties_df(prefix, prop=key, force=force)
    echo_df(properties_df)


_ORDERING_TEXT = ', '.join(
    f'{i}) {x}'
    for i, x in enumerate(DEFAULT_PRIORITY_LIST, start=1)
)


@main.command(help=f'Prioritize a CURIE from ordering: {_ORDERING_TEXT}')
@click.argument('curie')
def prioritize(curie: str):
    """Prioritize a CURIE."""
    priority_curie = get_priority_curie(curie)
    click.secho(priority_curie)


@main.command()
@click.option('-i', '--file-in', type=click.File('r'), default=sys.stdin)
@click.option('-o', '--file-out', type=click.File('w'), default=sys.stdout)
@click.option('--column', type=int, default=0, show_default=True)
@click.option('--sep', default='\t', show_default=True)
def recurify(file_in, file_out, column: int, sep: str):
    """Remap a column in a given file stream."""
    remap_file_stream(file_in=file_in, file_out=file_out, column=column, sep=sep)


@main.command()
@prefix_argument
@verbose_option
@force_option
def alts(prefix: str, force: bool):
    """Page through alt ids in a namespace."""
    id_to_alts = get_id_to_alts(prefix, force=force)
    click.echo_via_pager('\n'.join(
        f'{identifier}\t{alt}'
        for identifier, alts in id_to_alts.items()
        for alt in alts
    ))


@main.command()
@verbose_option
def cache():
    """Cache all resources."""
    for obo in iter_nomenclature_plugins():
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
    for directory in os.listdir(RAW_DIRECTORY):
        d = os.path.join(RAW_DIRECTORY, directory)
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


@main.command()
def ls():
    """List how big all of the OBO files are."""
    entries = [
        (prefix, os.path.getsize(path))
        for prefix, path in iter_cached_obo()
    ]
    entries = [
        (prefix, humanize.naturalsize(size), '✅' if not has_nomenclature_plugin(prefix) else '❌')
        for prefix, size in sorted(entries, key=itemgetter(1), reverse=True)
    ]
    click.echo(tabulate(entries, headers=['Source', 'Size', 'OBO']))


@main.command()
@click.argument('text')
@click.option('--name', is_flag=True)
def normalize(text: str, name: bool):
    """Normalize a prefix or CURIE."""
    if ':' in text:  # it's a curie
        s = ':'.join(normalize_curie(text))
    else:
        s = normalize_prefix(text)
    if name:
        name = get_name_by_curie(s)
        s = f'{s} ! {name}'
    click.echo(s)


@main.command()
@verbose_option
@click.option('-f', '--file', type=click.File('w'))
def remapping(file):
    """Make a canonical remapping."""
    canonicalizer = Canonicalizer.get_default()
    print('input', 'canonical', sep='\t', file=file)
    for source, target in canonicalizer.iterate_flat_mapping():
        print(source, target, sep='\t', file=file)


main.add_command(aws.aws)
main.add_command(cli_database.database)

if __name__ == '__main__':
    main()
