# -*- coding: utf-8 -*-

"""PyOBO's Gilda utilities."""

from typing import Iterable, Optional, Union

import gilda.term
from gilda.generate_terms import filter_out_duplicates
from gilda.grounder import Grounder
from gilda.process import normalize
from tqdm import tqdm

from pyobo import get_id_name_mapping, get_id_synonyms_mapping, get_ids
from pyobo.getters import NoBuild
from pyobo.utils.io import multidict

__all__ = [
    "get_grounder",
    "get_gilda_terms",
]


def get_grounder(
    prefix: Union[str, Iterable[str]], unnamed: Optional[Iterable[str]] = None
) -> Grounder:
    """Get a Gilda grounder for the given namespace."""
    unnamed = set() if unnamed is None else set(unnamed)
    if isinstance(prefix, str):
        prefix = [prefix]

    terms = []
    for p in prefix:
        try:
            p_terms = list(get_gilda_terms(p, use_identifiers=p in unnamed))
        except NoBuild:
            continue
        else:
            terms.extend(p_terms)
    terms = filter_out_duplicates(terms)
    terms = multidict((term.norm_text, term) for term in terms)
    return Grounder(terms)


def get_gilda_terms(prefix: str, use_identifiers: bool = False) -> Iterable[gilda.term.Term]:
    """Get gilda terms for the given namespace."""
    id_to_name = get_id_name_mapping(prefix)
    for identifier, name in tqdm(id_to_name.items(), desc="mapping names"):
        yield gilda.term.Term(
            norm_text=normalize(name),
            text=name,
            db=prefix,
            id=identifier,
            entry_name=name,
            status="name",
            source=prefix,
        )

    id_to_synonyms = get_id_synonyms_mapping(prefix)
    for identifier, synonyms in tqdm(id_to_synonyms.items(), desc="mapping synonyms"):
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
            )

    if use_identifiers:
        for identifier in tqdm(get_ids(prefix), desc="mapping identifiers"):
            yield gilda.term.Term(
                norm_text=normalize(identifier),
                text=identifier,
                db=prefix,
                id=identifier,
                entry_name=None,
                status="identifier",
                source=prefix,
            )
