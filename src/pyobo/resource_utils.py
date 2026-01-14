"""Resource utilities for PyOBO."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import click
import pandas as pd
from more_click import verbose_option
from zenodo_client import Zenodo

from .constants import (
    ALTS_DATA_RECORD,
    ALTS_FILE,
    DEFINITIONS_FILE,
    DEFINITIONS_RECORD,
    JAVERT_FILE,
    JAVERT_RECORD,
    OOH_NA_NA_FILE,
    OOH_NA_NA_RECORD,
    PROPERTIES_FILE,
    PROPERTIES_RECORD,
    RELATIONS_FILE,
    RELATIONS_RECORD,
    SPECIES_FILE,
    SPECIES_RECORD,
    SYNONYMS_FILE,
    SYNONYMS_RECORD,
)

__all__ = [
    "ensure_alts",
    "ensure_definitions",
    "ensure_inspector_javert",
    "ensure_inspector_javert_df",
    "ensure_ooh_na_na",
    "ensure_properties",
    "ensure_relations",
    "ensure_species",
    "ensure_synonyms",
]


@lru_cache(maxsize=1)
def _get_zenodo() -> Zenodo:
    """Get the cached Zenodo client."""
    return Zenodo()


def _get_parts(_concept_rec_id, _record_id, version) -> Sequence[str]:
    """Get sequence to use in :func:`pystow.ensure`.

    .. note::

        Corresponds to :data:`pyobo.constants.DATABASE_MODULE`.
    """
    return ["pyobo", "database", version]


def _ensure(record_id: str | int, name: str, force: bool = False) -> str:
    rv = _get_zenodo().download_latest(
        record_id=record_id, name=name, parts=_get_parts, force=force
    )
    return rv.as_posix()


def ensure_ooh_na_na(force: bool = False) -> str:
    """Ensure that the Ooh Na Na Nomenclature Database is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.OOH_NA_NA_RECORD`
    """
    return _ensure(record_id=OOH_NA_NA_RECORD, name=OOH_NA_NA_FILE, force=force)


def ensure_inspector_javert(force: bool = False) -> str:
    """Ensure that the Inspector Javert's Xref Database is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.JAVERT_RECORD`
    """
    return _ensure(record_id=JAVERT_RECORD, name=JAVERT_FILE, force=force)


def ensure_inspector_javert_df(force: bool = False) -> pd.DataFrame:
    """Ensure the inspector javert database as a dataframe."""
    path = ensure_inspector_javert(force=force)
    return pd.read_csv(path, sep="\t", dtype=str)


def ensure_synonyms(force: bool = False) -> str:
    """Ensure that the Synonym Database is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.SYNONYMS_RECORD`
    """
    return _ensure(record_id=SYNONYMS_RECORD, name=SYNONYMS_FILE, force=force)


def ensure_alts(force: bool = False) -> str:
    """Ensure that the alt data is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.ALTS_DATA_RECORD`
    """
    return _ensure(record_id=ALTS_DATA_RECORD, name=ALTS_FILE, force=force)


def ensure_species(force: bool = False) -> str:
    """Ensure that the species data is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.SPECIES_RECORD`
    """
    return _ensure(record_id=SPECIES_RECORD, name=SPECIES_FILE, force=force)


def ensure_definitions(force: bool = False) -> str:
    """Ensure that the definitions data is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.DEFINITIONS_RECORD`
    """
    return _ensure(record_id=DEFINITIONS_RECORD, name=DEFINITIONS_FILE, force=force)


def ensure_properties(force: bool = False) -> str:
    """Ensure that the properties data is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.PROPERTIES_RECORD`
    """
    return _ensure(record_id=PROPERTIES_RECORD, name=PROPERTIES_FILE, force=force)


def ensure_relations(force: bool = False) -> str:
    """Ensure that the relations data is downloaded/built.

    .. seealso::

        :data:`pyobo.constants.RELATIONS_RECORD`
    """
    return _ensure(record_id=RELATIONS_RECORD, name=RELATIONS_FILE, force=force)


@click.command()
@verbose_option
@click.option("-f", "--force", is_flag=True)
def main(force: bool):
    """Ensure resources are available."""
    for f in [
        ensure_ooh_na_na,
        ensure_synonyms,
        ensure_alts,
        ensure_inspector_javert,
        ensure_definitions,
        ensure_properties,
        ensure_relations,
    ]:
        doc = f.__doc__
        if doc is None:
            continue
        click.secho(doc.splitlines()[0], fg="green", bold=True)
        path = f(force=force)
        click.echo(path)


if __name__ == "__main__":
    main()
