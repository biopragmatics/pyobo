"""PyOBO's Gilda utilities."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, cast

import bioregistry
import ssslm
from ssslm import GildaGrounder, literal_mappings_to_gilda
from tqdm.auto import tqdm
from typing_extensions import Unpack

from pyobo.api import (
    get_id_name_mapping,
    get_ids,
    get_literal_mappings,
    get_literal_mappings_subset,
)
from pyobo.constants import GetOntologyKwargs
from pyobo.struct.reference import Reference

if TYPE_CHECKING:
    import gilda

__all__ = [
    "get_grounder",
    "iter_gilda_prediction_tuples",
]

logger = logging.getLogger(__name__)


# TODO the only place this is used is in Biomappings -
#  might be better to directly move it there
def iter_gilda_prediction_tuples(
    prefix: str,
    relation: str = "skos:exactMatch",
    *,
    grounder: gilda.Grounder | None = None,
    identifiers_are_names: bool = False,
    strict: bool = False,
) -> Iterable[tuple[str, str, str, str, str, str, str, str, float]]:
    """Iterate over prediction tuples for a given prefix."""
    if grounder is None:
        import gilda.api

        grounder = gilda.api.grounder
    grounder_ = GildaGrounder(grounder)
    id_name_mapping = get_id_name_mapping(prefix, strict=strict)
    it = tqdm(
        id_name_mapping.items(), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="name"
    )
    for identifier, name in it:
        norm_identifier = _normalize_identifier(prefix, identifier)
        for scored_match in grounder_.get_matches(name):
            yield (
                prefix,
                norm_identifier,
                name,
                relation,
                scored_match.prefix,
                _normalize_identifier(scored_match.prefix, scored_match.identifier),
                name,
                "semapv:LexicalMatching",
                round(scored_match.score, 3),
            )

    if identifiers_are_names:
        it = tqdm(get_ids(prefix), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="id")
        for identifier in it:
            norm_identifier = _normalize_identifier(prefix, identifier)
            for scored_match in grounder_.get_matches(identifier):
                yield (
                    prefix,
                    norm_identifier,
                    identifier,
                    relation,
                    scored_match.prefix,
                    _normalize_identifier(scored_match.prefix, scored_match.identifier),
                    identifier,
                    "semapv:LexicalMatching",
                    scored_match.score,
                )


def _normalize_identifier(prefix: str, identifier: str) -> str:
    """Normalize the identifier."""
    resource = bioregistry.get_resource(prefix)
    if resource is None:
        raise KeyError
    return resource.miriam_standardize_identifier(identifier) or identifier


def normalize_identifier(prefix: str, identifier: str) -> str:
    """Normalize the identifier."""
    warnings.warn(
        "normalization to MIRIAM is deprecated, please update to using Bioregistry standard identifiers",
        DeprecationWarning,
        stacklevel=2,
    )
    return _normalize_identifier(prefix, identifier)


def get_grounder(*args: Any, **kwargs: Any) -> gilda.Grounder:
    """Get a grounder."""
    warnings.warn("use pyobo.ner.get_grounder", DeprecationWarning, stacklevel=2)
    import pyobo.ner

    grounder = cast(ssslm.ner.GildaGrounder, pyobo.get_grounder(*args, **kwargs))
    return grounder._grounder


def get_gilda_terms(prefix: str, *, skip_obsolete: bool = False, **kwargs) -> Iterable[gilda.Term]:
    """Get gilda terms."""
    warnings.warn(
        "use pyobo.get_literal_mappings() directly and convert to gilda yourself",
        DeprecationWarning,
        stacklevel=2,
    )
    yield from literal_mappings_to_gilda(
        get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs)
    )


def get_gilda_term_subset(
    source: str,
    ancestors: str | Sequence[str],
    *,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Iterable[gilda.Term]:
    """Get a subset of terms."""
    warnings.warn(
        "use pyobo.get_literal_mappings_subset() directly and convert to gilda yourself",
        DeprecationWarning,
        stacklevel=2,
    )
    if isinstance(ancestors, str):
        ancestors = [ancestors]

    yield from literal_mappings_to_gilda(
        get_literal_mappings_subset(
            source,
            ancestors=[Reference.from_curie(a) for a in ancestors],
            skip_obsolete=skip_obsolete,
            **kwargs,
        )
    )
