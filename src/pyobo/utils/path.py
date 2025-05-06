"""Utilities for building paths."""

import enum
import logging
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from curies import Reference
from pystow import VersionHint

from ..constants import CACHE_SUBDIRECTORY_NAME, RAW_MODULE, RELATION_SUBDIRECTORY_NAME

__all__ = [
    "CacheArtifact",
    "ensure_df",
    "ensure_path",
    "get_cache_path",
    "get_relation_cache_path",
    "prefix_directory_join",
]

logger = logging.getLogger(__name__)


def prefix_directory_join(
    prefix: str,
    *parts: str,
    name: str | None = None,
    version: VersionHint = None,
    ensure_exists: bool = True,
) -> Path:
    """Join in the prefix directory."""
    return RAW_MODULE.module(prefix).join(
        *parts,
        name=name,
        ensure_exists=ensure_exists,
        version=version,
    )


def ensure_path(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: str | None = None,
    force: bool = False,
    backend: Literal["requests", "urllib"] = "urllib",
    verify: bool = True,
    **download_kwargs: Any,
) -> Path:
    """Download a file if it doesn't exist."""
    if verify:
        download_kwargs = {"backend": backend}
    else:
        if backend != "requests":
            logger.warning("using requests since verify=False")
        download_kwargs = {"backend": "requests", "verify": False}

    path = RAW_MODULE.module(prefix).ensure(
        *parts,
        url=url,
        name=name,
        force=force,
        version=version,
        download_kwargs=download_kwargs,
    )
    return path


def ensure_df(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: str | None = None,
    force: bool = False,
    sep: str = "\t",
    dtype=str,
    verify: bool = True,
    backend: Literal["requests", "urllib"] = "urllib",
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    _path = ensure_path(
        prefix,
        *parts,
        url=url,
        version=version,
        name=name,
        force=force,
        verify=verify,
        backend=backend,
    )
    return pd.read_csv(_path, sep=sep, dtype=dtype, **kwargs)


class CacheArtifact(enum.Enum):
    """An enumeration for."""

    names = "names.tsv.gz"
    definitions = "definitions.tsv.gz"
    species = "species.tsv.gz"
    mappings = "mappings.tsv.gz"
    relations = "relations.tsv.gz"
    alts = "alt_ids.tsv.gz"
    typedefs = "typedefs.tsv.gz"
    literal_mappings = "literal_mappings.tsv.gz"
    references = "references.tsv.gz"
    obsoletes = "obsolete.tsv.gz"

    literal_properties = "literal_properties.tsv.gz"
    object_properties = "object_properties.tsv.gz"

    nodes = "nodes.tsv.gz"
    edges = "edges.tsv.gz"

    prefixes = "prefixes.json"
    metadata = "metadata.json"


def get_cache_path(
    ontology: str,
    name: CacheArtifact,
    *,
    version: str | None = None,
) -> Path:
    """Get a cache path."""
    return prefix_directory_join(
        ontology, CACHE_SUBDIRECTORY_NAME, name=name.value, version=version
    )


def get_relation_cache_path(
    ontology: str,
    reference: Reference,
    *,
    version: str | None = None,
) -> Path:
    """Get a relation cache path."""
    return prefix_directory_join(
        ontology, RELATION_SUBDIRECTORY_NAME, name=f"{reference.curie}.tsv", version=version
    )
