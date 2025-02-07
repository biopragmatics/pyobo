"""PyOBO's Gilda utilities."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import bioregistry
from tqdm.auto import tqdm
from typing_extensions import Unpack

from pyobo import (
    Reference,
    get_id_name_mapping,
    get_ids,
    get_literal_mappings,
    get_literal_mappings_subset,
)
from pyobo.constants import GetOntologyKwargs
from pyobo.ner.api import ground

if TYPE_CHECKING:
    import gilda

__all__ = [
    "get_grounder",
    "iter_gilda_prediction_tuples",
]

logger = logging.getLogger(__name__)


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
    id_name_mapping = get_id_name_mapping(prefix, strict=strict)
    it = tqdm(
        id_name_mapping.items(), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="name"
    )
    for identifier, name in it:
        norm_identifier = normalize_identifier(prefix, identifier)
        for scored_match in ground(grounder, name):
            yield (
                prefix,
                norm_identifier,
                name,
                relation,
                scored_match.prefix,
                normalize_identifier(scored_match.prefix, scored_match.identifier),
                scored_match.name,
                "semapv:LexicalMatching",
                round(scored_match.score, 3),
            )

    if identifiers_are_names:
        it = tqdm(get_ids(prefix), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="id")
        for identifier in it:
            norm_identifier = normalize_identifier(prefix, identifier)
            for scored_match in ground(grounder, identifier):
                yield (
                    prefix,
                    norm_identifier,
                    identifier,
                    relation,
                    scored_match.prefix,
                    normalize_identifier(scored_match.prefix, scored_match.identifier),
                    scored_match.name,
                    "semapv:LexicalMatching",
                    scored_match.score,
                )


def normalize_identifier(prefix: str, identifier: str) -> str:
    """Normalize the identifier."""
    resource = bioregistry.get_resource(prefix)
    if resource is None:
        raise KeyError
    return resource.miriam_standardize_identifier(identifier) or identifier


def get_grounder(*args, **kwargs):
    """Get a grounder."""
    warnings.warn("use pyobo.ner.get_grounder", DeprecationWarning, stacklevel=2)
    import pyobo.ner

    return pyobo.ner.get_grounder(*args, **kwargs)


def get_gilda_terms(prefix: str, *, skip_obsolete: bool = False, **kwargs) -> Iterable[gilda.Term]:
    """Get gilda terms."""
    warnings.warn(
        "use pyobo.get_literal_mappings() directly and convert to gilda yourself",
        DeprecationWarning,
        stacklevel=2,
    )
    from pyobo.ner.api import _lm_to_gilda

    for lm in get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs):
        yield _lm_to_gilda(lm)


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
    from pyobo.ner.api import _lm_to_gilda

    if isinstance(ancestors, str):
        ancestors = [ancestors]
    for lm in get_literal_mappings_subset(
        source,
        ancestors=[Reference.from_curie(a) for a in ancestors],
        skip_obsolete=skip_obsolete,
        **kwargs,
    ):
        yield _lm_to_gilda(lm)
