# -*- coding: utf-8 -*-

"""CLI for PyOBO Database Generation."""

import sys

import click
from more_click import verbose_option
from zenodo_client import update_zenodo

from .utils import directory_option, force_option, no_strict_option, zenodo_option
from ..constants import (
    ALTS_DATA_RECORD,
    DEFINITIONS_RECORD,
    JAVERT_RECORD,
    OOH_NA_NA_RECORD,
    PROPERTIES_RECORD,
    RELATIONS_RECORD,
    SYNONYMS_RECORD,
    TYPEDEFS_RECORD,
)
from ..database.sql.cli import database_sql
from ..getters import db_output_helper
from ..xrefdb.xrefs_pipeline import (
    _iter_alts,
    _iter_definitions,
    _iter_metadata,
    _iter_ooh_na_na,
    _iter_properties,
    _iter_relations,
    _iter_synonyms,
    _iter_typedefs,
    _iter_xrefs,
)

__all__ = [
    "main",
]


@click.group(name="database")
def main():
    """Build the PyOBO Database."""


main.add_command(database_sql)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
@click.pass_context
def build(ctx: click.Context, directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Build all databases."""
    if no_strict and zenodo:
        click.secho("Must be strict before uploading", fg="red")
        sys.exit(1)

    click.secho("Collecting metadata and building", fg="cyan", bold=True)
    ctx.invoke(metadata, directory=directory, no_strict=no_strict, force=force)
    click.secho("Alternate Identifiers", fg="cyan", bold=True)
    ctx.invoke(alts, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Synonyms", fg="cyan", bold=True)
    ctx.invoke(synonyms, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Xrefs", fg="cyan", bold=True)
    ctx.invoke(xrefs, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Names", fg="cyan", bold=True)
    ctx.invoke(names, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Definitions", fg="cyan", bold=True)
    ctx.invoke(definitions, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Properties", fg="cyan", bold=True)
    ctx.invoke(properties, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Relations", fg="cyan", bold=True)
    ctx.invoke(relations, directory=directory, zenodo=zenodo, no_strict=no_strict)
    click.secho("Typedefs", fg="cyan", bold=True)
    ctx.invoke(typedefs, directory=directory, zenodo=zenodo, no_strict=no_strict)


@main.command()
@verbose_option
@directory_option
@force_option
@no_strict_option
def metadata(directory: str, no_strict: bool, force: bool):
    """Make the prefix-metadata dump."""
    db_output_helper(
        _iter_metadata,
        "metadata",
        ("prefix", "version", "date"),
        strict=not no_strict,
        force=force,
        directory=directory,
        use_gzip=False,
    )


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def names(directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Make the prefix-identifier-name dump."""
    paths = db_output_helper(
        _iter_ooh_na_na,
        "names",
        ("prefix", "identifier", "name"),
        strict=not no_strict,
        force=force,
        directory=directory,
    )
    if zenodo:
        # see https://zenodo.org/record/4020486
        update_zenodo(OOH_NA_NA_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def definitions(directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Make the prefix-identifier-definition dump."""
    paths = db_output_helper(
        _iter_definitions,
        "definitions",
        ("prefix", "identifier", "definition"),
        strict=not no_strict,
        force=force,
        directory=directory,
        skip_set={"kegg.pathway", "kegg.genes", "kegg.genome", "umls"},
    )
    if zenodo:
        # see https://zenodo.org/record/4637061
        update_zenodo(DEFINITIONS_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def typedefs(directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Make the typedef prefix-identifier-name dump."""
    paths = db_output_helper(
        _iter_typedefs,
        "typedefs",
        ("prefix", "typedef_prefix", "identifier", "name"),
        strict=not no_strict,
        force=force,
        directory=directory,
        use_gzip=False,
        skip_set={"ncbigene", "kegg.pathway", "kegg.genes", "kegg.genome"},
    )
    if zenodo:
        # see https://zenodo.org/record/4644013
        update_zenodo(TYPEDEFS_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def alts(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the prefix-alt-id dump."""
    paths = db_output_helper(
        _iter_alts,
        "alts",
        ("prefix", "identifier", "alt"),
        directory=directory,
        force=force,
        strict=not no_strict,
        skip_set={"kegg.pathway", "kegg.genes", "kegg.genome", "umls"},
    )
    if zenodo:
        # see https://zenodo.org/record/4021476
        update_zenodo(ALTS_DATA_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def synonyms(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the prefix-identifier-synonym dump."""
    paths = db_output_helper(
        _iter_synonyms,
        "synonyms",
        ("prefix", "identifier", "synonym"),
        directory=directory,
        force=force,
        strict=not no_strict,
        skip_set={"kegg.pathway", "kegg.genes", "kegg.genome"},
    )
    if zenodo:
        # see https://zenodo.org/record/4021482
        update_zenodo(SYNONYMS_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def relations(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the relation dump."""
    paths = db_output_helper(
        _iter_relations,
        "relations",
        (
            "source_prefix",
            "source_identifier",
            "relation_prefix",
            "relation_identifier",
            "target_prefix",
            "target_identifier",
        ),
        directory=directory,
        force=force,
        strict=not no_strict,
        summary_detailed=(0, 2, 3),  # second column corresponds to relation type
    )
    if zenodo:
        # see https://zenodo.org/record/4625167
        update_zenodo(RELATIONS_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def properties(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the properties dump."""
    paths = db_output_helper(
        _iter_properties,
        "properties",
        ("prefix", "identifier", "property", "value"),
        directory=directory,
        force=force,
        strict=not no_strict,
        summary_detailed=(0, 2),  # second column corresponds to property type
    )
    if zenodo:
        # see https://zenodo.org/record/4625172
        update_zenodo(PROPERTIES_RECORD, paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def xrefs(directory: str, zenodo: bool, force: bool, no_strict: bool):  # noqa: D202
    """Make the prefix-identifier-xref dump."""
    paths = db_output_helper(
        _iter_xrefs,
        "xrefs",
        ("prefix", "identifier", "xref_prefix", "xref_identifier", "provenance"),
        directory=directory,
        force=force,
        strict=not no_strict,
        summary_detailed=(0, 2),  # second column corresponds to xref prefix
    )
    if zenodo:
        # see https://zenodo.org/record/4021477
        update_zenodo(JAVERT_RECORD, paths)


if __name__ == "__main__":
    main()
