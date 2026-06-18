"""Utilities for high-level API."""

from typing import TypeAlias

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
    "SimpleReferenceHint",
    "VersionError",
    "get_version",
    "get_version_from_kwargs",
    "get_version_pins",
    "pin_version",
]


SimpleReferenceHint: TypeAlias = str | curies.Reference | ReferenceTuple


def _get_pi(reference: SimpleReferenceHint, /) -> Reference:
    """Resolve a reference hint."""
    if isinstance(reference, Reference):
        return reference
    if isinstance(reference, ReferenceTuple | curies.Reference):
        return Reference.from_reference(reference)
    if isinstance(reference, str):
        return Reference.from_curie(reference)
    raise TypeError(f"unexpected type {type(reference)}")
