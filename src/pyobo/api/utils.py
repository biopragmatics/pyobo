"""Utilities for high-level API."""

import curies
from curies import ReferenceTuple

from ..identifier_utils import Reference
from ..utils.ver import (
    VersionError,
    get_version,
    get_version_from_kwargs,
    get_version_pins,
    pin_version,
)

__all__ = [
    "VersionError",
    "get_version",
    "get_version_from_kwargs",
    "get_version_pins",
    "pin_version",
]


def _get_pi(
    prefix: str | curies.Reference | ReferenceTuple, identifier: str | None = None, /
) -> Reference:
    if isinstance(prefix, ReferenceTuple | curies.Reference):
        if identifier is not None:
            raise ValueError("unexpected non-none value passed as second positional argument")
        return Reference.from_reference(prefix)
    if isinstance(prefix, str) and identifier is None:
        return Reference.from_curie(prefix)
    raise NotImplementedError
