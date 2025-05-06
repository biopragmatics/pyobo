"""CLI for PyOBO Database Generation."""

import logging
import warnings
from collections.abc import Iterable
from pathlib import Path

import bioregistry
import click
from more_click import verbose_option
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import Unpack
from zenodo_client import update_zenodo

from .database_utils import (
    IterHelperHelperDict,
    _iter_alts,
    _iter_definitions,
    _iter_edges,
    _iter_mappings,
    _iter_names,
    _iter_properties,
    _iter_relations,
    _iter_species,
    _iter_synonyms,
    _iter_typedefs,
    _iter_xrefs,
    iter_helper_helper,
)
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
    DatabaseKwargs,
)
from ..getters import db_output_helper, get_ontology

__all__ = [
    "main",
]

logger = logging.getLogger(__name__)


@click.group(name="database")
def main():
    """Build the PyOBO Database."""


skip_pyobo_option = click.option(
    "--skip-pyobo",
    is_flag=True,
    help="Skip prefixes whose ontologies are implemented as PyOBO sources",
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
        click.secho("Mappings", fg="cyan", bold=True)
        ctx.invoke(mappings, **updated_kwargs)
        click.secho("Names", fg="cyan", bold=True)
        ctx.invoke(names, **updated_kwargs)
        click.secho("Definitions", fg="cyan", bold=True)
        ctx.invoke(definitions, **updated_kwargs)
        click.secho("Properties", fg="cyan", bold=True)
        ctx.invoke(properties, **updated_kwargs)
        click.secho("Relations", fg="cyan", bold=True)
        ctx.invoke(relations, **updated_kwargs)
        click.secho("Edges", fg="cyan", bold=True)
        ctx.invoke(edges, **updated_kwargs)
        click.secho("Typedefs", fg="cyan", bold=True)
        ctx.invoke(typedefs, **updated_kwargs)
        click.secho("Species", fg="cyan", bold=True)
        ctx.invoke(species, **updated_kwargs)


@database_annotate
def cache(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Cache all things."""
    if zenodo:
        click.echo("no zenodo for caching")

    kwargs["force_process"] = True
    with logging_redirect_tqdm():
        for _ in iter_helper_helper(get_ontology, **kwargs):
            # this pass intentional to consume the iterable
            pass


@database_annotate
def metadata(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-metadata dump."""
    from ..api import get_metadata

    def _iter_metadata(
        **kwargs: Unpack[IterHelperHelperDict],
    ) -> Iterable[tuple[str, str, str, bool]]:
        for prefix, data in iter_helper_helper(get_metadata, **kwargs):
            version = data["version"]
            logger.debug(f"[{prefix}] using version {version}")
            yield prefix, version, data["date"], bioregistry.is_deprecated(prefix)

    it = _iter_metadata(**kwargs)
    db_output_helper(
        it,
        "metadata",
        ("prefix", "version", "date", "deprecated"),
        use_gzip=False,
        directory=directory,
    )
    if zenodo:
        click.secho("No Zenodo record for metadata", fg="red")


@database_annotate
def names(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-name dump."""
    it = _iter_names(**kwargs)
    with logging_redirect_tqdm():
        paths = db_output_helper(
            it,
            "names",
            ("prefix", "identifier", "name"),
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4020486
        update_zenodo(OOH_NA_NA_RECORD, paths)


@database_annotate
def species(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-species dump."""
    with logging_redirect_tqdm():
        it = _iter_species(**kwargs)
        paths = db_output_helper(
            it,
            "species",
            ("prefix", "identifier", "species"),
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/5334738
        update_zenodo(SPECIES_RECORD, paths)


def _extend_skip_set(kwargs: DatabaseKwargs, skip_set: set[str]) -> None:
    ss = kwargs.get("skip_set")
    if ss is None:
        kwargs["skip_set"] = skip_set
    else:
        ss.update(skip_set)


@database_annotate
def definitions(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-definition dump."""
    with logging_redirect_tqdm():
        _extend_skip_set(kwargs, {"kegg.pathway", "kegg.genes", "kegg.genome", "umls"})
        it = _iter_definitions(**kwargs)
        paths = db_output_helper(
            it,
            "definitions",
            ("prefix", "identifier", "definition"),
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4637061
        update_zenodo(DEFINITIONS_RECORD, paths)


@database_annotate
def typedefs(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the typedef prefix-identifier-name dump."""
    with logging_redirect_tqdm():
        _extend_skip_set(kwargs, {"ncbigene", "kegg.pathway", "kegg.genes", "kegg.genome"})
        it = _iter_typedefs(**kwargs)
        paths = db_output_helper(
            it,
            "typedefs",
            ("prefix", "typedef_prefix", "identifier", "name"),
            use_gzip=False,
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4644013
        update_zenodo(TYPEDEFS_RECORD, paths)


@database_annotate
def alts(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-alt-id dump."""
    with logging_redirect_tqdm():
        _extend_skip_set(kwargs, {"kegg.pathway", "kegg.genes", "kegg.genome", "umls"})
        it = _iter_alts(**kwargs)
        paths = db_output_helper(
            it,
            "alts",
            ("prefix", "identifier", "alt"),
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4021476
        update_zenodo(ALTS_DATA_RECORD, paths)


@database_annotate
def synonyms(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-synonym dump."""
    with logging_redirect_tqdm():
        _extend_skip_set(kwargs, {"kegg.pathway", "kegg.genes", "kegg.genome"})
        it = _iter_synonyms(**kwargs)
        paths = db_output_helper(
            it,
            "synonyms",
            ("prefix", "identifier", "synonym"),
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4021482
        update_zenodo(SYNONYMS_RECORD, paths)


@database_annotate
def relations(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the relation dump."""
    with logging_redirect_tqdm():
        it = _iter_relations(**kwargs)
        paths = db_output_helper(
            it,
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
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4625167
        update_zenodo(RELATIONS_RECORD, paths)


@database_annotate
def edges(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the edges dump."""
    with logging_redirect_tqdm():
        it = _iter_edges(**kwargs)
        db_output_helper(
            it,
            "edges",
            (
                ":START_ID",
                ":TYPE",
                ":END_ID",
                "provenance",
            ),
            directory=directory,
        )
    if zenodo:
        raise NotImplementedError


@database_annotate
def properties(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the properties dump."""
    with logging_redirect_tqdm():
        it = _iter_properties(**kwargs)
        paths = db_output_helper(
            it,
            "properties",
            ("prefix", "identifier", "property", "value"),
            summary_detailed=(0, 2),  # second column corresponds to property type
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4625172
        update_zenodo(PROPERTIES_RECORD, paths)


@database_annotate
def xrefs(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the prefix-identifier-xref dump."""
    warnings.warn("Use pyobo.database.mappings instead", DeprecationWarning, stacklevel=2)
    with logging_redirect_tqdm():
        it = _iter_xrefs(**kwargs)
        paths = db_output_helper(
            it,
            "xrefs",
            ("prefix", "identifier", "xref_prefix", "xref_identifier", "provenance"),
            summary_detailed=(0, 2),  # second column corresponds to xref prefix
            directory=directory,
        )
    if zenodo:
        # see https://zenodo.org/record/4021477
        update_zenodo(JAVERT_RECORD, paths)


@database_annotate
def mappings(zenodo: bool, directory: Path, **kwargs: Unpack[DatabaseKwargs]) -> None:
    """Make the SSSOM dump."""
    columns = [
        "subject_id",
        "object_id",
        "predicate_id",
        "mapping_justification",
        "mapping_source",
    ]
    with logging_redirect_tqdm():
        it = _iter_mappings(**kwargs)
        db_output_helper(
            it,
            "mappings",
            columns,
            directory=directory,
        )
    if zenodo:
        raise NotImplementedError("need to do initial manual upload of SSSOM build")


if __name__ == "__main__":
    logging.captureWarnings(True)
    with logging_redirect_tqdm():
        main()
