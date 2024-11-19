"""CLI for PyOBO Database Generation."""

import logging
from typing import TypedDict, Unpack

import click
from more_click import verbose_option
from tqdm.contrib.logging import logging_redirect_tqdm
from zenodo_client import update_zenodo

from .utils import (
    Clickable,
    directory_option,
    force_option,
    force_process_option,
    strict_option,
    zenodo_option,
)
from ..constants import (
    ALTS_DATA_RECORD,
    DEFINITIONS_RECORD,
    JAVERT_RECORD,
    OOH_NA_NA_RECORD,
    PROPERTIES_RECORD,
    RELATIONS_RECORD,
    SPECIES_RECORD,
    SYNONYMS_RECORD,
    TYPEDEFS_RECORD,
)
from ..getters import db_output_helper
from ..xrefdb.xrefs_pipeline import (
    _iter_alts,
    _iter_definitions,
    _iter_metadata,
    _iter_names,
    _iter_properties,
    _iter_relations,
    _iter_species,
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


skip_pyobo_option = click.option(
    "--skip-pyobo", help="Skip prefixes whose ontologies are implemented as PyOBO sources"
)
skip_below_option = click.option(
    "--skip-below", help="Skip prefixes lexically sorted below the given one"
)


def database_annotate(f: Clickable) -> Clickable:
    """Add appropriate decorators to database CLI functions."""
    decorators = [
        main.command(),
        zenodo_option,
        verbose_option,
        directory_option,
        force_option,
        force_process_option,
        strict_option,
        skip_pyobo_option,
        skip_below_option,
    ]
    for decorator in decorators:
        f = decorator(f)
    return f


class DatabaseKwargs(TypedDict):
    """Keyword arguments for database CLI functions."""

    directory: str
    strict: bool
    force: bool
    force_process: bool
    skip_pyobo: bool
    skip_below: str | None


def _update_database_kwargs(kwargs: DatabaseKwargs) -> DatabaseKwargs:
    updated_kwargs = dict(kwargs)
    updated_kwargs.update(force=False, force_process=False)
    # FIXME get typing right on next line
    return updated_kwargs  # type:ignore


@database_annotate
@click.pass_context
def build(ctx: click.Context, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Build all databases."""
    # if no_strict and zenodo:
    #    click.secho("Must be strict before uploading", fg="red")
    #    sys.exit(1)
    with logging_redirect_tqdm():
        click.secho("Collecting metadata and building", fg="cyan", bold=True)
        # note that this is the only one that needs a force=force
        ctx.invoke(metadata, **kwargs)

        # After running once, we don't want to force or re-process.
        # All the other arguments come along for the ride!
        updated_kwargs = _update_database_kwargs(kwargs)

        click.secho("Alternate Identifiers", fg="cyan", bold=True)
        ctx.invoke(alts, **updated_kwargs)
        click.secho("Synonyms", fg="cyan", bold=True)
        ctx.invoke(synonyms, **updated_kwargs)
        click.secho("Xrefs", fg="cyan", bold=True)
        ctx.invoke(xrefs, **updated_kwargs)
        click.secho("Names", fg="cyan", bold=True)
        ctx.invoke(names, **updated_kwargs)
        click.secho("Definitions", fg="cyan", bold=True)
        ctx.invoke(definitions, **updated_kwargs)
        click.secho("Properties", fg="cyan", bold=True)
        ctx.invoke(properties, **updated_kwargs)
        click.secho("Relations", fg="cyan", bold=True)
        ctx.invoke(relations, **updated_kwargs)
        click.secho("Typedefs", fg="cyan", bold=True)
        ctx.invoke(typedefs, **updated_kwargs)
        click.secho("Species", fg="cyan", bold=True)
        ctx.invoke(species, **updated_kwargs)


@database_annotate
def metadata(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-metadata dump."""
    db_output_helper(
        _iter_metadata,
        "metadata",
        ("prefix", "version", "date", "deprecated"),
        use_gzip=False,
        **kwargs,
    )
    if zenodo:
        click.secho("No Zenodo record for metadata", fg="red")


@database_annotate
def names(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-name dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_names,
            "names",
            ("prefix", "identifier", "name"),
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4020486
        update_zenodo(OOH_NA_NA_RECORD, paths)


@database_annotate
def species(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-species dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_species,
            "species",
            ("prefix", "identifier", "species"),
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/5334738
        update_zenodo(SPECIES_RECORD, paths)


@database_annotate
def definitions(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-definition dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_definitions,
            "definitions",
            ("prefix", "identifier", "definition"),
            skip_set={"kegg.pathway", "kegg.genes", "kegg.genome", "umls"},
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4637061
        update_zenodo(DEFINITIONS_RECORD, paths)


@database_annotate
def typedefs(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the typedef prefix-identifier-name dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_typedefs,
            "typedefs",
            ("prefix", "typedef_prefix", "identifier", "name"),
            use_gzip=False,
            skip_set={"ncbigene", "kegg.pathway", "kegg.genes", "kegg.genome"},
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4644013
        update_zenodo(TYPEDEFS_RECORD, paths)


@database_annotate
def alts(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-alt-id dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_alts,
            "alts",
            ("prefix", "identifier", "alt"),
            skip_set={"kegg.pathway", "kegg.genes", "kegg.genome", "umls"},
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4021476
        update_zenodo(ALTS_DATA_RECORD, paths)


@database_annotate
def synonyms(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-synonym dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_synonyms,
            "synonyms",
            ("prefix", "identifier", "synonym"),
            skip_set={"kegg.pathway", "kegg.genes", "kegg.genome"},
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4021482
        update_zenodo(SYNONYMS_RECORD, paths)


@database_annotate
def relations(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the relation dump."""
    with logging_redirect_tqdm():
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
            summary_detailed=(0, 2, 3),  # second column corresponds to relation type
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4625167
        update_zenodo(RELATIONS_RECORD, paths)


@database_annotate
def properties(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the properties dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_properties,
            "properties",
            ("prefix", "identifier", "property", "value"),
            summary_detailed=(0, 2),  # second column corresponds to property type
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4625172
        update_zenodo(PROPERTIES_RECORD, paths)


@database_annotate
def xrefs(zenodo: bool, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-xref dump."""
    with logging_redirect_tqdm():
        paths = db_output_helper(
            _iter_xrefs,
            "xrefs",
            ("prefix", "identifier", "xref_prefix", "xref_identifier", "provenance"),
            summary_detailed=(0, 2),  # second column corresponds to xref prefix
            **kwargs,
        )
    if zenodo:
        # see https://zenodo.org/record/4021477
        update_zenodo(JAVERT_RECORD, paths)


if __name__ == "__main__":
    logging.captureWarnings(True)
    with logging_redirect_tqdm():
        main()
