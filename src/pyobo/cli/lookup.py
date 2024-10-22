"""CLI for PyOBO lookups."""

import json
import sys
from typing import Optional

import bioregistry
import click
from more_click import verbose_option

from .utils import (
    echo_df,
    force_option,
    no_strict_option,
    prefix_argument,
    version_option,
)
from ..api import (
    get_ancestors,
    get_descendants,
    get_filtered_properties_df,
    get_filtered_relations_df,
    get_filtered_xrefs,
    get_hierarchy,
    get_id_definition_mapping,
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_ids,
    get_metadata,
    get_name,
    get_name_by_curie,
    get_properties_df,
    get_relations_df,
    get_typedef_df,
    get_xrefs_df,
)
from ..identifier_utils import normalize_curie

__all__ = [
    "lookup",
]


@click.group()
def lookup():
    """Lookup resources."""


@lookup.command()
@prefix_argument
@click.option("-t", "--target")
@verbose_option
@force_option
@no_strict_option
@version_option
def xrefs(prefix: str, target: str, force: bool, no_strict: bool, version: Optional[str]):
    """Page through xrefs for the given namespace to the second given namespace."""
    if target:
        target = bioregistry.normalize_prefix(target)
        filtered_xrefs = get_filtered_xrefs(
            prefix, target, force=force, strict=not no_strict, version=version
        )
        click.echo_via_pager(
            "\n".join(f"{identifier}\t{_xref}" for identifier, _xref in filtered_xrefs.items())
        )
    else:
        all_xrefs_df = get_xrefs_df(prefix, force=force, strict=not no_strict, version=version)
        echo_df(all_xrefs_df)


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@version_option
def metadata(prefix: str, force: bool, version: Optional[str]):
    """Print the metadata for the given namespace."""
    metadata = get_metadata(prefix, force=force, version=version)
    click.echo(json.dumps(metadata, indent=2))


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@no_strict_option
@version_option
def ids(prefix: str, force: bool, no_strict: bool, version: Optional[str]):
    """Page through the identifiers of entities in the given namespace."""
    id_list = get_ids(prefix, force=force, strict=not no_strict, version=version)
    click.echo_via_pager("\n".join(id_list))


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@no_strict_option
@click.option("-i", "--identifier")
@version_option
def names(
    prefix: str, identifier: Optional[str], force: bool, no_strict: bool, version: Optional[str]
):
    """Page through the identifiers and names of entities in the given namespace."""
    id_to_name = get_id_name_mapping(prefix, force=force, strict=not no_strict, version=version)
    if identifier is None:
        _help_page_mapping(id_to_name)
    else:
        name = id_to_name.get(identifier)
        if name is None:
            click.secho(f"No name available for {identifier}", fg="red")
        else:
            click.echo(name)


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@no_strict_option
@click.option("-i", "--identifier")
@version_option
def species(
    prefix: str, identifier: Optional[str], force: bool, no_strict: bool, version: Optional[str]
):
    """Page through the identifiers and species of entities in the given namespace."""
    id_to_species = get_id_species_mapping(
        prefix, force=force, strict=not no_strict, version=version
    )
    if identifier is None:
        _help_page_mapping(id_to_species)
    else:
        species = id_to_species.get(identifier)
        if species is None:
            click.secho(f"No species available for {identifier}", fg="red")
        else:
            click.echo(species)


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@click.option("-i", "--identifier")
@version_option
def definitions(prefix: str, identifier: Optional[str], force: bool, version: Optional[str]):
    """Page through the identifiers and definitions of entities in the given namespace."""
    id_to_definition = get_id_definition_mapping(prefix, force=force, version=version)
    if identifier is None:
        _help_page_mapping(id_to_definition)
    else:
        definition = id_to_definition.get(identifier)
        if definition is None:
            click.secho(f"No definition available for {identifier}", fg="red")
        else:
            click.echo(definition)


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@version_option
def typedefs(prefix: str, force: bool, version: Optional[str]):
    """Page through the identifiers and names of typedefs in the given namespace."""
    df = get_typedef_df(prefix, force=force, version=version)
    echo_df(df)


def _help_page_mapping(id_to_name):
    click.echo_via_pager("\n".join("\t".join(item) for item in id_to_name.items()))


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@version_option
def synonyms(prefix: str, force: bool, version: Optional[str]):
    """Page through the synonyms for entities in the given namespace."""
    if ":" in prefix:
        _prefix, identifier = normalize_curie(prefix)
        if _prefix is None or identifier is None:
            click.secho(f"could not normalize {prefix}")
            return sys.exit(1)
        name = get_name(_prefix, identifier)
        id_to_synonyms = get_id_synonyms_mapping(_prefix, force=force)
        click.echo(f"Synonyms for {_prefix}:{identifier} ! {name}")
        for synonym in id_to_synonyms.get(identifier, []):
            click.echo(synonym)
    else:  # it's a prefix
        id_to_synonyms = get_id_synonyms_mapping(prefix, force=force, version=version)
        click.echo_via_pager(
            "\n".join(
                f"{identifier}\t{_synonym}"
                for identifier, _synonyms in id_to_synonyms.items()
                for _synonym in _synonyms
            )
        )


@lookup.command()
@prefix_argument
@click.option(
    "--relation", help="CURIE for the relationship or just the ID if local to the ontology"
)
@click.option("--target", help="Prefix for the target")
@verbose_option
@no_strict_option
@force_option
@click.option("--summarize", is_flag=True)
@version_option
def relations(
    prefix: str,
    relation: str,
    target: str,
    force: bool,
    no_strict: bool,
    summarize: bool,
    version: Optional[str],
):
    """Page through the relations for entities in the given namespace."""
    if relation is None:
        relations_df = get_relations_df(prefix, force=force, strict=not no_strict, version=version)
        if summarize:
            click.echo(relations_df[relations_df.columns[2]].value_counts())
        else:
            echo_df(relations_df)
    else:
        curie = normalize_curie(relation)
        if curie[1] is None:  # that's the identifier
            click.secho(f"not valid curie, assuming local to {prefix}", fg="yellow")
            curie = prefix, relation

        if target is not None:
            norm_target = bioregistry.normalize_prefix(target)
            if norm_target is None:
                raise ValueError
            relations_df = get_filtered_relations_df(
                prefix, relation=curie, force=force, strict=not no_strict, target=norm_target
            )
        else:
            raise NotImplementedError(f"can not filter by target prefix {target}")


@lookup.command()
@prefix_argument
@click.option("--include-part-of", is_flag=True)
@click.option("--include-has-member", is_flag=True)
@verbose_option
@force_option
@version_option
def hierarchy(
    prefix: str,
    include_part_of: bool,
    include_has_member: bool,
    force: bool,
    version: Optional[str],
):
    """Page through the hierarchy for entities in the namespace."""
    h = get_hierarchy(
        prefix,
        include_part_of=include_part_of,
        include_has_member=include_has_member,
        force=force,
        version=version,
    )
    click.echo_via_pager("\n".join("\t".join(row) for row in h.edges()))


@lookup.command()
@prefix_argument
@click.argument("identifier")
@verbose_option
@force_option
@version_option
def ancestors(prefix: str, identifier: str, force: bool, version: Optional[str]):
    """Look up ancestors."""
    curies = get_ancestors(prefix=prefix, identifier=identifier, force=force, version=version)
    for curie in sorted(curies or []):
        click.echo(f"{curie}\t{get_name_by_curie(curie, version=version)}")


@lookup.command()
@prefix_argument
@click.argument("identifier")
@verbose_option
@force_option
@version_option
def descendants(prefix: str, identifier: str, force: bool, version: Optional[str]):
    """Look up descendants."""
    curies = get_descendants(prefix=prefix, identifier=identifier, force=force, version=version)
    for curie in sorted(curies or []):
        click.echo(f"{curie}\t{get_name_by_curie(curie, version=version)}")


@lookup.command()
@prefix_argument
@click.option("-k", "--key")
@verbose_option
@force_option
@version_option
def properties(prefix: str, key: Optional[str], force: bool, version: Optional[str]):
    """Page through the properties for entities in the given namespace."""
    if key is None:
        properties_df = get_properties_df(prefix, force=force, version=version)
    else:
        properties_df = get_filtered_properties_df(prefix, prop=key, force=force)
    echo_df(properties_df)


@lookup.command()
@prefix_argument
@verbose_option
@force_option
@click.option("-i", "--identifier")
@version_option
def alts(prefix: str, identifier: Optional[str], force: bool, version: Optional[str]):
    """Page through alt ids in a namespace."""
    id_to_alts = get_id_to_alts(prefix, force=force, version=version)
    if identifier is None:
        click.echo_via_pager(
            "\n".join(
                f"{identifier}\t{alt}" for identifier, alts in id_to_alts.items() for alt in alts
            )
        )
    else:
        _alts = id_to_alts.get(identifier)
        if _alts is None:
            click.secho(f"No alternate identifiers for {identifier}", fg="red")
        else:
            click.echo("\n".join(_alts))
