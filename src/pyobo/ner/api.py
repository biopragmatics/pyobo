"""NER functionality."""

from __future__ import annotations

from collections.abc import Iterable
from subprocess import CalledProcessError
from typing import TYPE_CHECKING, Any

import ssslm
from ssslm import LiteralMapping, Match
from ssslm.ner import GildaGrounder
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api import get_literal_mappings
from pyobo.constants import GetOntologyKwargs, check_should_use_tqdm
from pyobo.getters import NoBuildError
from pyobo.struct.reference import Reference

if TYPE_CHECKING:
    import gilda

__all__ = [
    "get_grounder",
]


def get_grounder(
    prefixes: str | Iterable[str],
    *,
    grounder_cls: type[gilda.Grounder] | None = None,
    versions: None | str | Iterable[str | None] | dict[str, str] = None,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> ssslm.Grounder:
    """Get a grounder for the given prefix(es)."""
    literal_mappings: list[LiteralMapping] = []
    disable = not check_should_use_tqdm(kwargs)
    for prefix, kwargs["version"] in tqdm(
        _clean_prefix_versions(prefixes, versions=versions),
        leave=False,
        disable=disable,
    ):
        try:
            literal_mappings.extend(
                get_literal_mappings(
                    prefix,
                    skip_obsolete=skip_obsolete,
                    **kwargs,
                )
            )
        except (NoBuildError, CalledProcessError):
            continue

    return ssslm.make_grounder(literal_mappings, implementation="gilda", grounder_cls=grounder_cls)


def literal_mappings_to_gilda(
    literal_mappings: Iterable[LiteralMapping],
) -> Iterable[gilda.Term]:
    """Yield literal mappings as gilda terms.

    This is different from the upstream ssslm impl
    because it injects species.
    """
    for _lm in literal_mappings:
        yield _lm.to_gilda()


def _clean_prefix_versions(
    prefixes: str | Iterable[str],
    versions: None | str | Iterable[str | None] | dict[str, str] = None,
) -> list[tuple[str, str | None]]:
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    else:
        prefixes = list(prefixes)
    if versions is None:
        versions = [None] * len(prefixes)
    elif isinstance(versions, str):
        versions = [versions]
    elif isinstance(versions, dict):
        versions = [versions.get(prefix) for prefix in prefixes]
    else:
        versions = list(versions)
    if len(prefixes) != len(versions):
        raise ValueError

    return list(zip(prefixes, versions, strict=True))


def _ensure_list(reference: Reference | list[Reference]) -> list[Reference]:
    if isinstance(reference, Reference):
        return [reference]
    return reference
