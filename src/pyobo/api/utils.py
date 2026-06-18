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
    reference: str | curies.Reference | ReferenceTuple, _unused: str | None = None, /
) -> Reference:
    if _unused is not None:
        raise ValueError("unexpected non-none value passed as second positional argument")
    if isinstance(reference, ReferenceTuple | curies.Reference):
        return Reference.from_reference(reference)
    if isinstance(reference, str) and _unused is None:
        return Reference.from_curie(reference)
    raise TypeError(f"unexpected type {type(reference)}")
