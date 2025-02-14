"""CLI for PyOBO lookups."""

import json
import sys
from collections.abc import Mapping

import bioregistry
import click
from more_click import verbose_option
from typing_extensions import Unpack

from .utils import (
    Clickable,
    echo_df,
    force_option,
    force_process_option,
    prefix_argument,
    strict_option,
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
    get_mappings_df,
    get_metadata,
    get_name,
    get_properties_df,
    get_relations_df,
    get_typedef_df,
    get_xrefs_df,
)
from ..constants import LookupKwargs
from ..getters import get_ontology
from ..struct.reference import _parse_str_or_curie_or_uri

__all__ = [
    "lookup",
]


@click.group()
def lookup():
    """Lookup resources."""


def lookup_annotate(f: Clickable) -> Clickable:
    """Add appropriate decorators to lookup CLI functions."""
    for decorator in [
        lookup.command(),
        prefix_argument,
        verbose_option,
        force_option,
        force_process_option,
        strict_option,
        version_option,
    ]:
        f = decorator(f)
    return f


identifier_option = click.option("-i", "--identifier")


@lookup_annotate
@click.option("-t", "--target")
def xrefs(target: str, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through xrefs for the given namespace to the second given namespace."""
    if target:
        target_norm = bioregistry.normalize_prefix(target)
        filtered_xrefs = get_filtered_xrefs(xref_prefix=target_norm, **kwargs)
        click.echo_via_pager(
            "\n".join(f"{identifier}\t{_xref}" for identifier, _xref in filtered_xrefs.items())
        )
    else:
        all_xrefs_df = get_xrefs_df(**kwargs)
        echo_df(all_xrefs_df)


@lookup_annotate
@click.option("--include-names", is_flag=True)
@click.option("-t", "--target")
def mappings(include_names: bool, target: str | None, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through mappings for the given namespace."""
    mappings_df = get_mappings_df(names=include_names, **kwargs)
    if target:
        target_norm = bioregistry.normalize_prefix(target)
        if target_norm is None:
            raise ValueError
        idx = mappings_df["object_id"].map(
            lambda x: bioregistry.normalize_prefix(x.split(":")[0]) == target_norm
        )
        mappings_df = mappings_df[idx]
    echo_df(mappings_df)


@lookup_annotate
def metadata(**kwargs: Unpack[LookupKwargs]) -> None:
    """Print the metadata for the given namespace."""
    metadata = get_metadata(**kwargs)
    click.echo(json.dumps(metadata, indent=2))


@lookup_annotate
def ids(**kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the identifiers of entities in the given namespace."""
    id_list = get_ids(**kwargs)
    if not id_list:
        click.secho("no data", fg="red")
    else:
        click.echo_via_pager("\n".join(id_list))


@lookup_annotate
@identifier_option
def names(identifier: str | None, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the identifiers and names of entities in the given namespace."""
    id_to_name = get_id_name_mapping(**kwargs)
    _help_page_mapping(id_to_name, identifier=identifier)


@lookup_annotate
@identifier_option
def species(identifier: str | None, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the identifiers and species of entities in the given namespace."""
    id_to_species = get_id_species_mapping(**kwargs)
    _help_page_mapping(id_to_species, identifier=identifier)


@lookup_annotate
@identifier_option
def definitions(identifier: str | None, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the identifiers and definitions of entities in the given namespace."""
    id_to_definition = get_id_definition_mapping(**kwargs)
    _help_page_mapping(id_to_definition, identifier=identifier)


@lookup_annotate
def typedefs(**kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the identifiers and names of typedefs in the given namespace."""
    df = get_typedef_df(**kwargs)
    echo_df(df)


def _help_page_mapping(id_to_name: Mapping[str, str], *, identifier: str | None = None) -> None:
    if not id_to_name:
        click.secho("no data", fg="red")
    elif identifier:
        value = id_to_name.get(identifier)
        if value:
            click.echo(value)
        else:
            click.secho(f"no data for {identifier}", fg="red")
    else:
        click.echo_via_pager("\n".join("\t".join(item) for item in id_to_name.items()))


@lookup_annotate
@identifier_option
def synonyms(identifier: str | None, **kwargs: Unpack[LookupKwargs]) -> None:
    """Page through the synonyms for entities in the given namespace."""
    id_to_synonyms = get_id_synonyms_mapping(**kwargs)
    if identifier is None:
        click.echo_via_pager(
            "\n".join(
                f"{identifier}\t{_synonym}"
                for identifier, _synonyms in id_to_synonyms.items()
                for _synonym in _synonyms
            )
        )
    else:
        synonyms = id_to_synonyms.get(identifier, [])
        if not synonyms:
            click.secho(f"No synonyms available for {identifier}", fg="red")
        else:
            click.echo_via_pager("\n".join(synonyms))


@lookup_annotate
@click.option(
    "--relation", help="CURIE for the relationship or just the ID if local to the ontology"
)
@click.option("--target", help="Prefix for the target")
@click.option("--summarize", is_flag=True)
def relations(
    relation: str,
    target: str,
    summarize: bool,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Page through the relations for entities in the given namespace."""
    if relation is None:
        relations_df = get_relations_df(**kwargs)
        if summarize:
            click.echo(relations_df[relations_df.columns[2]].value_counts())
        else:
            echo_df(relations_df)
    else:
        relation_reference = _parse_str_or_curie_or_uri(relation, strict=False)
        if relation_reference is None:
            click.secho(f"not a valid curie: {relation}", fg="red")
            raise sys.exit(1)

        if target is not None:
            norm_target = bioregistry.normalize_prefix(target)
            if norm_target is None:
                raise ValueError
            relations_df = get_filtered_relations_df(
                relation=relation_reference,
                target=norm_target,
                **kwargs,
            )
        else:
            raise NotImplementedError(f"can not filter by target prefix {target}")


@lookup_annotate
@click.option("--include-part-of", is_flag=True)
@click.option("--include-has-member", is_flag=True)
def hierarchy(
    include_part_of: bool,
    include_has_member: bool,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Page through the hierarchy for entities in the namespace."""
    h = get_hierarchy(
        include_part_of=include_part_of,
        include_has_member=include_has_member,
        **kwargs,
    )
    if h.number_of_edges() == 0:
        click.secho("no data", fg="red")
    else:
        click.echo_via_pager("\n".join(f"{u.curie}\t{v.curie}" for u, v in h.edges()))


@lookup_annotate
@click.argument("identifier")
def ancestors(
    identifier: str,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Look up ancestors."""
    # note, prefix is passed via kwargs
    ancestors = get_ancestors(identifier=identifier, **kwargs)
    for ancestor in sorted(ancestors or []):
        click.echo(f"{ancestor.curie}\t{get_name(ancestor, version=kwargs['version'])}")


@lookup_annotate
@click.argument("identifier")
def descendants(
    identifier: str,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Look up descendants."""
    # note, prefix is passed via kwargs
    descendants = get_descendants(identifier=identifier, **kwargs)
    for descendant in sorted(descendants or []):
        click.echo(f"{descendant.curie}\t{get_name(descendant, version=kwargs['version'])}")


@lookup_annotate
@click.option("-k", "--key")
def properties(
    key: str | None,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Page through the properties for entities in the given namespace."""
    if key is None:
        properties_df = get_properties_df(**kwargs)
    else:
        properties_df = get_filtered_properties_df(prop=key, **kwargs)
    echo_df(properties_df)


@lookup_annotate
@identifier_option
def alts(
    identifier: str | None,
    **kwargs: Unpack[LookupKwargs],
) -> None:
    """Page through alt ids in a namespace."""
    id_to_alts = get_id_to_alts(**kwargs)
    _help_page_mapping(id_to_alts, identifier=identifier)


@lookup_annotate
def prefixes(**kwargs: Unpack[LookupKwargs]) -> None:
    """Page through prefixes appearing in an ontology."""
    ontology = get_ontology(**kwargs)
    for prefix in sorted(ontology._get_prefixes(), key=str.casefold):
        click.echo(prefix)
