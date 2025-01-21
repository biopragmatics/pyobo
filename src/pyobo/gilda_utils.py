"""PyOBO's Gilda utilities."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from subprocess import CalledProcessError

import bioregistry
import gilda.api
import gilda.term
from gilda.grounder import Grounder
from gilda.term import filter_out_duplicates
from tqdm.auto import tqdm
from typing_extensions import Unpack

from pyobo import (
    get_descendants,
    get_id_name_mapping,
    get_id_species_mapping,
    get_ids,
    get_literal_mappings,
    get_obsolete,
)
from pyobo.api.utils import get_version_from_kwargs
from pyobo.constants import GetOntologyKwargs, check_should_use_tqdm
from pyobo.getters import NoBuildError
from pyobo.utils.io import multidict

__all__ = [
    "get_gilda_terms",
    "get_grounder",
    "iter_gilda_prediction_tuples",
]

logger = logging.getLogger(__name__)


def iter_gilda_prediction_tuples(
    prefix: str,
    relation: str = "skos:exactMatch",
    *,
    grounder: Grounder | None = None,
    identifiers_are_names: bool = False,
    strict: bool = False,
) -> Iterable[tuple[str, str, str, str, str, str, str, str, float]]:
    """Iterate over prediction tuples for a given prefix."""
    if grounder is None:
        grounder = gilda.api.grounder
    id_name_mapping = get_id_name_mapping(prefix, strict=strict)
    it = tqdm(
        id_name_mapping.items(), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="name"
    )
    for identifier, name in it:
        for scored_match in grounder.ground(name):
            target_prefix = scored_match.term.db.lower()
            yield (
                prefix,
                normalize_identifier(prefix, identifier),
                name,
                relation,
                target_prefix,
                normalize_identifier(target_prefix, scored_match.term.id),
                scored_match.term.entry_name,
                "semapv:LexicalMatching",
                round(scored_match.score, 3),
            )

    if identifiers_are_names:
        it = tqdm(get_ids(prefix), desc=f"[{prefix}] gilda tuples", unit_scale=True, unit="id")
        for identifier in it:
            for scored_match in grounder.ground(identifier):
                target_prefix = scored_match.term.db.lower()
                yield (
                    prefix,
                    normalize_identifier(prefix, identifier),
                    identifier,
                    relation,
                    target_prefix,
                    normalize_identifier(target_prefix, scored_match.term.id),
                    scored_match.term.entry_name,
                    "semapv:LexicalMatching",
                    scored_match.score,
                )


def normalize_identifier(prefix: str, identifier: str) -> str:
    """Normalize the identifier."""
    resource = bioregistry.get_resource(prefix)
    if resource is None:
        raise KeyError
    return resource.miriam_standardize_identifier(identifier) or identifier


def get_grounder(
    prefixes: str | Iterable[str],
    *,
    unnamed: Iterable[str] | None = None,
    grounder_cls: type[Grounder] | None = None,
    versions: None | str | Iterable[str | None] | dict[str, str] = None,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Grounder:
    """Get a Gilda grounder for the given prefix(es)."""
    unnamed = set() if unnamed is None else set(unnamed)
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

    progress = check_should_use_tqdm(kwargs)
    terms: list[gilda.term.Term] = []
    for prefix, kwargs["version"] in zip(
        tqdm(prefixes, leave=False, disable=not progress), versions, strict=False
    ):
        try:
            p_terms = list(
                get_gilda_terms(
                    prefix,
                    identifiers_are_names=prefix in unnamed,
                    skip_obsolete=skip_obsolete,
                    **kwargs,
                )
            )
        except (NoBuildError, CalledProcessError):
            continue
        else:
            terms.extend(p_terms)
    terms = filter_out_duplicates(terms)
    terms_dict = multidict((term.norm_text, term) for term in terms)
    if grounder_cls is None:
        return Grounder(terms_dict)
    else:
        return grounder_cls(terms_dict)


def get_gilda_terms(
    prefix: str,
    *,
    identifiers_are_names: bool = False,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Iterable[gilda.term.Term]:
    """Get gilda terms for the given namespace."""
    if identifiers_are_names:
        raise NotImplementedError
    kwargs["version"] = get_version_from_kwargs(prefix, kwargs)  # type:ignore
    id_to_species = get_id_species_mapping(prefix, **kwargs)
    obsoletes = get_obsolete(prefix, **kwargs) if skip_obsolete else set()
    for synonym in get_literal_mappings(prefix, **kwargs):
        if synonym.reference.identifier in obsoletes:
            continue
        yield synonym.to_gilda(organism=id_to_species.get(synonym.reference.identifier))


def get_gilda_term_subset(
    source: str,
    ancestors: str | list[str],
    **kwargs: Unpack[GetOntologyKwargs],
) -> Iterable[gilda.term.Term]:
    """Get a subset of terms."""
    subset = {
        descendant
        for parent_curie in _ensure_list(ancestors)
        for descendant in get_descendants(*parent_curie.split(":")) or []
    }
    for term in get_gilda_terms(source, **kwargs):
        if bioregistry.curie_to_str(term.db, term.id) in subset:
            yield term


def _ensure_list(s: str | list[str]) -> list[str]:
    if isinstance(s, str):
        return [s]
    return s
