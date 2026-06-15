"""Utilities for high-level API."""

import warnings

import curies
from bioregistry import NormalizedNamableReference as Reference
from curies import ReferenceTuple

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
        return Reference(prefix=prefix.prefix, identifier=prefix.identifier)
    if isinstance(prefix, str) and identifier is None:
        return Reference.from_curie(prefix)
    if identifier is None:
        raise ValueError(
            "prefix was given as a string, so an identifier was expected to be passed as a string as well"
        )
    warnings.warn(
        "Passing a prefix and identifier as seperate arguments is deprecated. Please pass a curies.Reference or curies.ReferenceTuple in the first positional-only argument instead.",
        DeprecationWarning,
        stacklevel=4,  # this is 4 since this is (always?) called from inside a decorator
    )
    return Reference(prefix=prefix, identifier=identifier)
