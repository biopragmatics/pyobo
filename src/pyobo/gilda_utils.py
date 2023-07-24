# -*- coding: utf-8 -*-

"""PyOBO's Gilda utilities."""

import itertools as itt
import logging
from typing import Iterable, List, Optional, Tuple, Type, Union

import bioregistry
import gilda.api
import gilda.term
from gilda.grounder import Grounder
from gilda.process import normalize
from tqdm.auto import tqdm

from pyobo import (
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_ids,
)
from pyobo.getters import NoBuild
from pyobo.utils.io import multidict

__all__ = [
    "iter_gilda_prediction_tuples",
    "get_grounder",
    "get_gilda_terms",
]

logger = logging.getLogger(__name__)


_STATUSES = {"curated": 1, "name": 2, "synonym": 3, "former_name": 4}


def filter_out_duplicates(terms: List[gilda.term.Term]) -> List[gilda.term.Term]:
    """Filter out duplicates."""
    # TODO import from gilda.term import filter_out_duplicates when it gets moved,
    #  see https://github.com/indralab/gilda/pull/103
    logger.debug("filtering %d terms for uniqueness", len(terms))
    new_terms: List[gilda.term.Term] = [
        min(terms_group, key=_status_key)
        for _, terms_group in itt.groupby(sorted(terms, key=_term_key), key=_term_key)
    ]
    # Re-sort the terms
    new_terms = sorted(new_terms, key=lambda x: (x.text, x.db, x.id))
    logger.debug("got %d unique terms.", len(new_terms))
    return new_terms


def _status_key(term: gilda.term.Term) -> int:
    return _STATUSES[term.status]


def _term_key(term: gilda.term.Term) -> Tuple[str, str, str]:
    return term.db, term.id, term.text


def iter_gilda_prediction_tuples(
    prefix: str,
    relation: str = "skos:exactMatch",
    *,
    grounder: Optional[Grounder] = None,
    identifiers_are_names: bool = False,
    strict: bool = False,
) -> Iterable[Tuple[str, str, str, str, str, str, str, str, float]]:
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
    prefixes: Union[str, Iterable[str]],
    unnamed: Optional[Iterable[str]] = None,
    grounder_cls: Optional[Type[Grounder]] = None,
    versions: Union[None, str, Iterable[Union[str, None]]] = None,
    strict: bool = True,
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
    else:
        versions = list(versions)
    if len(prefixes) != len(versions):
        raise ValueError

    terms: List[gilda.term.Term] = []
    for prefix, version in zip(prefixes, versions):
        try:
            p_terms = list(
                get_gilda_terms(
                    prefix, identifiers_are_names=prefix in unnamed, version=version, strict=strict
                )
            )
        except NoBuild:
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
    identifiers_are_names: bool = False,
    version: Optional[str] = None,
    strict: bool = True,
) -> Iterable[gilda.term.Term]:
    """Get gilda terms for the given namespace."""
    id_to_name = get_id_name_mapping(prefix, version=version, strict=strict)
    id_to_species = get_id_species_mapping(prefix, version=version, strict=strict)

    it = tqdm(id_to_name.items(), desc=f"[{prefix}] mapping", unit_scale=True, unit="name")
    for identifier, name in it:
        yield gilda.term.Term(
            norm_text=normalize(name),
            text=name,
            db=prefix,
            id=identifier,
            entry_name=name,
            status="name",
            source=prefix,
            organism=id_to_species.get(identifier),
        )

    id_to_synonyms = get_id_synonyms_mapping(prefix, version=version)
    if id_to_synonyms:
        it = tqdm(
            id_to_synonyms.items(), desc=f"[{prefix}] mapping", unit_scale=True, unit="synonym"
        )
        for identifier, synonyms in it:
            name = id_to_name[identifier]
            for synonym in synonyms:
                yield gilda.term.Term(
                    norm_text=normalize(synonym),
                    text=synonym,
                    db=prefix,
                    id=identifier,
                    entry_name=name,
                    status="synonym",
                    source=prefix,
                    organism=id_to_species.get(identifier),
                )

    if identifiers_are_names:
        it = tqdm(get_ids(prefix), desc=f"[{prefix}] mapping", unit_scale=True, unit="id")
        for identifier in it:
            yield gilda.term.Term(
                norm_text=normalize(identifier),
                text=identifier,
                db=prefix,
                id=identifier,
                entry_name=None,
                status="identifier",
                source=prefix,
                organism=id_to_species.get(identifier),
            )
