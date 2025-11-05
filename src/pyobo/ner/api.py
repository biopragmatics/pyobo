"""NER functionality."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


def get_grounder(
    prefixes: str | Iterable[str],
    *,
    grounder_cls: type[gilda.Grounder] | None = None,
    versions: None | str | Iterable[str | None] | dict[str, str] = None,
    skip_obsolete: bool = False,
    raise_on_missing: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> ssslm.Grounder:
    """Get a grounder for the given prefix(es)."""
    all_literal_mappings: list[LiteralMapping] = []
    it = _clean_prefix_versions(prefixes, versions=versions)
    disable = len(it) == 1 or not check_should_use_tqdm(kwargs)
    for prefix, kwargs["version"] in tqdm(it, leave=False, disable=disable):
        try:
            literal_mappings = get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs)
        except (NoBuildError, CalledProcessError) as e:
            logger.warning("[%s] unable to get literal mappings: %s", prefix, e)
            continue
        else:
            if not literal_mappings:
                if raise_on_missing:
                    raise ValueError(f"no literal mappings were loaded for {prefix}")
                logger.warning("[%s] no literal mappings loaded", prefix)
            all_literal_mappings.extend(literal_mappings)

    return ssslm.make_grounder(
        all_literal_mappings, implementation="gilda", grounder_cls=grounder_cls
    )


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
