"""Version utils."""

from __future__ import annotations

import datetime
import json
import logging
import os
from functools import lru_cache
from typing import Annotated, Any, Literal, cast, overload

import bioversions
from pydantic import BaseModel, BeforeValidator
from pystow.utils import read_pydantic_json

from .path import CacheArtifact, prefix_directory_join
from ..constants import GetOntologyKwargs

logger = logging.getLogger(__name__)

__all__ = [
    "VersionError",
    "VersionMetadata",
    "get_version",
    "get_version_from_kwargs",
    "get_version_pins",
    "pin_version",
]


class VersionError(ValueError):
    """A catch-all for version getting failure."""


# docstr-coverage:excused `overload`
@overload
def get_version(prefix: str, *, strict: Literal[True] = ...) -> str: ...


# docstr-coverage:excused `overload`
@overload
def get_version(prefix: str, *, strict: Literal[False] = ...) -> str | None: ...


@lru_cache(None)
def get_version(prefix: str, *, strict: bool = False) -> str | None:
    """Get the version for the resource, if available.

    :param prefix: the resource name
    :param strict: Should an error be raised if no version is available?

    :returns: The version if available else None

    :raises VersionError: if the version is not available and strict mode is enabled
    """
    # Prioritize loaded environment variable PYOBO_VERSION_PINS dictionary
    if version := get_version_pins().get(prefix):
        return version

    if version := bioversions.get_version(prefix, strict=False):
        return version

    metadata_path = prefix_directory_join(
        prefix, name=CacheArtifact.metadata.value, ensure_exists=False
    )
    if metadata_path.exists():
        metadata = read_pydantic_json(metadata_path, VersionMetadata)
        if metadata.version:
            return metadata.version

    if strict:
        raise ValueError(
            f"[{prefix}] could not get version from bioversions nor lookup version cache"
        )

    return None


def get_version_from_kwargs(prefix: str, kwargs: GetOntologyKwargs) -> str | None:
    """Get the version for the resource based on generic keyword arguments."""
    if version := kwargs.get("version"):
        return version
    # it's okay if none gets returned after getting this far, we at least tried
    return get_version(prefix, strict=False)


def pin_version(prefix: str, version: str) -> None:
    """Pin the version."""
    get_version_pins()[prefix] = version


@lru_cache(1)
def get_version_pins() -> dict[str, str]:
    """Retrieve user-defined resource version pins.

    To set your own resource pins, set your machine's environmental variable
    "PYOBO_VERSION_PINS" to a JSON string containing string resource prefixes as keys
    and string versions of their respective resource as values. Constraining version
    pins will make PyOBO rely on cached versions of a resource. A user might want to pin
    resource versions that are used by PyOBO due to the fact that PyOBO will download
    the latest version of a resource if it is not pinned. This downloading process can
    lead to a slow-down in downstream applications that rely on PyOBO.
    """
    version_pins_str = os.getenv("PYOBO_VERSION_PINS")
    if not version_pins_str:
        return {}

    try:
        version_pins = cast(dict[str, str], json.loads(version_pins_str))
    except ValueError as e:
        logger.error(
            "The value for the environment variable PYOBO_VERSION_PINS "
            "must be a valid JSON string: %s",
            e,
        )
        return {}

    for prefix, version in list(version_pins.items()):
        if not isinstance(prefix, str) or not isinstance(version, str):
            logger.error(f"The prefix:{prefix} and version:{version} name must both be strings")
            del version_pins[prefix]

    logger.debug(
        f"These are the resource versions that are pinned.\n"
        f"{version_pins}. "
        f"\nPyobo will download the latest version of a resource if it's "
        f"not pinned.\nIf you want to use a specific version of a "
        f"resource, edit your PYOBO_VERSION_PINS environmental "
        f"variable which is a JSON string to include a prefix and version "
        f"name."
    )
    return version_pins


def _ensure_date(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            dt = datetime.datetime.fromisoformat(value)
        except Exception:
            return value
        else:
            return dt.date()
    return value


class VersionMetadata(BaseModel):
    """A model for version metadata information."""

    version: str | None = None
    date: Annotated[datetime.date | None, BeforeValidator(_ensure_date)] = None
