"""NER functionality."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeAlias

import ssslm
from ssslm import LiteralMapping
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api import get_literal_mappings
from pyobo.constants import GetOntologyKwargs, check_show_progress
from pyobo.struct import Reference

if TYPE_CHECKING:
    import gilda

__all__ = [
    "GrounderVersionsHint",
    "get_grounder",
]

logger = logging.getLogger(__name__)

GrounderVersionsHint: TypeAlias = str | Iterable[str | None] | dict[str, str]


def get_grounder(
    prefixes: str | Iterable[str],
    *,
    grounder_cls: type[gilda.Grounder] | None = None,
    versions: GrounderVersionsHint | None = None,
    skip_obsolete: bool = False,
    raise_on_missing: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> ssslm.Grounder[Reference]:
    """Get a grounder for the given prefix(es)."""
    all_literal_mappings: list[LiteralMapping[Reference]] = []
    prefix_version_pairs = _clean_prefix_versions(prefixes, versions=versions)
    disable = len(prefix_version_pairs) == 1 or not check_show_progress(kwargs)
    it = tqdm(prefix_version_pairs, leave=False, disable=disable, desc="Getting grounders")
    failures = []
    for prefix, kwargs["version"] in it:
        it.set_description(f"Getting grounder for {prefix}")
        try:
            literal_mappings = get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs)
        except Exception:
            logger.exception("[%s] unable to get literal mappings", prefix)
            failures.append(prefix)
            continue
        else:
            if not literal_mappings:
                if raise_on_missing:
                    raise ValueError(f"no literal mappings were loaded for {prefix}")
                logger.warning("[%s] no literal mappings loaded", prefix)
            all_literal_mappings.extend(literal_mappings)

    if len(failures) > 1:
        tqdm.write("failure summary for get_grounder():")
        for failure in failures:
            tqdm.write(f"- {failure}")

    return ssslm.make_grounder(
        all_literal_mappings, implementation="gilda", grounder_cls=grounder_cls
    )


def _clean_prefix_versions(
    prefixes: str | Iterable[str],
    versions: GrounderVersionsHint | None = None,
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
