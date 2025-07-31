"""NER functionality."""

from __future__ import annotations

from collections.abc import Iterable
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

import ssslm
from ssslm import LiteralMapping
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api import get_literal_mappings
from pyobo.constants import GetOntologyKwargs, check_should_use_tqdm
from pyobo.getters import NoBuildError

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
    it = _clean_prefix_versions(prefixes, versions=versions)
    disable = len(it) == 1 or not check_should_use_tqdm(kwargs)
    for prefix, kwargs["version"] in tqdm(it, leave=False, disable=disable):
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
