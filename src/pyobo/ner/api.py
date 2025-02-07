"""NER functionality."""

from __future__ import annotations

from collections.abc import Iterable
from subprocess import CalledProcessError
from typing import TYPE_CHECKING, Any

import biosynonyms
from biosynonyms import LiteralMapping
from pydantic import BaseModel
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api import get_literal_mappings, get_species
from pyobo.constants import GetOntologyKwargs, check_should_use_tqdm
from pyobo.getters import NoBuildError
from pyobo.struct.reference import Reference
from pyobo.utils.io import multidict

if TYPE_CHECKING:
    import gilda

__all__ = [
    "Match",
    "get_grounder",
    "ground",
    "ground_best",
]


class Match(BaseModel):
    """A wrapped match."""

    reference: Reference
    score: float

    @classmethod
    def from_scored_match(cls, scored_match: gilda.ScoredMatch) -> Match:
        """Wrap a Gilda scored match."""
        return cls(
            reference=Reference(
                prefix=scored_match.term.db,
                identifier=scored_match.term.id,
                name=scored_match.term.entry_name,
            ),
            score=scored_match.score,
        )

    @property
    def prefix(self) -> str:
        """Get the scored match's term's prefix."""
        return self.reference.prefix

    @property
    def identifier(self) -> str:
        """Get the scored match's term's identifier."""
        return self.reference.identifier

    @property
    def name(self) -> str:
        """Get the scored match's term's name."""
        if not self.reference.name:
            raise ValueError
        return self.reference.name


def ground(grounder: gilda.Grounder, text: str, **kwargs: Any) -> list[Match]:
    """Repack scored matches to be easier to use."""
    return [
        Match.from_scored_match(scored_match) for scored_match in grounder.ground(text, **kwargs)
    ]


def ground_best(grounder: gilda.Grounder, text: str, **kwargs: Any) -> Match | None:
    """Repack scored matches to be easier to use."""
    sm = grounder.ground_best(text, **kwargs)
    return Match.from_scored_match(sm) if sm else None


def get_grounder(
    prefixes: str | Iterable[str],
    *,
    grounder_cls: type[gilda.Grounder] | None = None,
    versions: None | str | Iterable[str | None] | dict[str, str] = None,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> gilda.Grounder:
    """Get a Gilda grounder for the given prefix(es)."""
    literal_mappings: list[biosynonyms.LiteralMapping] = []
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

    return _build_grounder(literal_mappings, grounder_cls=grounder_cls)


def literal_mappings_to_gilda(
    literal_mappings: Iterable[biosynonyms.LiteralMapping],
) -> Iterable[gilda.Term]:
    """Yield literal mappings as gilda terms.

    This is different from the upstream biosynonyms impl
    because it injects species.
    """
    for lm in literal_mappings:
        yield _lm_to_gilda(lm)


def _build_grounder(
    literal_mappings: list[LiteralMapping], grounder_cls: type[gilda.Grounder] | None = None
):
    from gilda.term import filter_out_duplicates

    gilda_terms = filter_out_duplicates(literal_mappings_to_gilda(literal_mappings))
    terms_dict = multidict((term.norm_text, term) for term in gilda_terms)

    if grounder_cls is None:
        from gilda import Grounder

        return Grounder(terms_dict)
    else:
        return grounder_cls(terms_dict)


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


def _lm_to_gilda(mapping: LiteralMapping) -> gilda.Term:
    return mapping.to_gilda(organism=get_species(mapping.reference))


def _ensure_list(reference: Reference | list[Reference]) -> list[Reference]:
    if isinstance(reference, Reference):
        return [reference]
    return reference
