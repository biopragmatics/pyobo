"""Use synonyms from OBO to normalize names."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Union

import bioregistry

from .api import names
from .utils.io import multisetdict

__all__ = [
    "ground",
    "Normalizer",
    "OboNormalizer",
    "MultiNormalizer",
    "NormalizationResult",
]

logger = logging.getLogger(__name__)

NormalizationSuccess = tuple[str, str, str]
NormalizationFailure = tuple[None, None, str]
NormalizationResult = Union[NormalizationSuccess, NormalizationFailure]


class Normalizer(ABC):
    """A normalizer."""

    id_to_name: dict[str, str]
    id_to_synonyms: dict[str, list[str]]

    #: A mapping from all synonyms to the set of identifiers that they point to.
    #: In a perfect world, each would only be a single element.
    synonym_to_identifiers_mapping: dict[str, set[str]]
    #: A mapping from normalized names to the actual ones that they came from
    norm_name_to_name: dict[str, set[str]]

    def __init__(
        self,
        id_to_name: dict[str, str],
        id_to_synonyms: dict[str, list[str]],
        remove_prefix: Optional[str] = None,
    ) -> None:
        """Initialize the normalizer.

        :param id_to_name: An identifier to name dictionary.
        :param id_to_synonyms: An identifier to list of synonyms dictionary.
        :param remove_prefix: A prefix to be removed from the identifiers. Useful for nomenclatures like ChEBI.
        """
        self.id_to_name = id_to_name
        self.id_to_synonyms = id_to_synonyms
        self.synonym_to_identifiers_mapping = multisetdict(
            self._iterate_synonyms_to_identifiers(
                id_to_name=self.id_to_name,
                id_to_synonyms=self.id_to_synonyms,
                remove_prefix=remove_prefix,
            )
        )
        self.norm_name_to_name = self._get_norm_name_to_names(self.synonym_to_identifiers_mapping)

    @classmethod
    def _get_norm_name_to_names(cls, synonyms: Iterable[str]) -> dict[str, set[str]]:
        return multisetdict((cls._normalize_text(synonym), synonym) for synonym in synonyms)

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.strip().strip('"').strip("'").lower()
        text = normalize_dashes(text)
        text = text.replace("-", "")  # remove all dashes
        text = text.replace(" ", "")  # remove all spaces
        return text

    @staticmethod
    def _iterate_synonyms_to_identifiers(
        *,
        id_to_name: Mapping[str, str],
        id_to_synonyms: Mapping[str, Iterable[str]],
        remove_prefix: Optional[str] = None,
    ) -> Iterable[tuple[str, str]]:
        if remove_prefix is not None:
            remove_prefix = f'{remove_prefix.lower().rstrip(":")}:'

        # Add name
        for identifier, name in id_to_name.items():
            if remove_prefix and identifier.lower().startswith(remove_prefix):
                identifier = identifier[len(remove_prefix) :]

            yield name, identifier

        # Add synonyms
        for identifier, synonyms in id_to_synonyms.items():
            if remove_prefix and identifier.lower().startswith(remove_prefix):
                identifier = identifier[len(remove_prefix) :]

            for synonym in synonyms:
                # it might overwrite but this is probably always due to alternate ids
                yield synonym, identifier

    def get_names(self, query: str) -> list[str]:
        """Get all names to which the query text maps."""
        norm_text = self._normalize_text(query)
        return list(self.norm_name_to_name.get(norm_text, []))

    @abstractmethod
    def normalize(self, query: str) -> NormalizationResult:
        """Try and normalize a name to a identifier and canonical name."""
        raise NotImplementedError


@lru_cache
def get_normalizer(prefix: str) -> Normalizer:
    """Get an OBO normalizer."""
    norm_prefix = bioregistry.normalize_prefix(prefix)
    if norm_prefix is None:
        raise ValueError(f"unhandled prefix: {prefix}")
    logger.info("getting obo normalizer for %s", norm_prefix)
    normalizer = OboNormalizer(norm_prefix)
    logger.debug(
        "normalizer for %s with %s name lookups",
        normalizer.prefix,
        len(normalizer.norm_name_to_name),
    )
    return normalizer


def ground(prefix: Union[str, Iterable[str]], query: str) -> NormalizationResult:
    """Normalize a string given the prefix's labels and synonyms.

    :param prefix: If a string, only grounds against that namespace. If a list, will try grounding
     against all in that order
    :param query: The string to try grounding
    """
    if isinstance(prefix, str):
        normalizer = get_normalizer(prefix)
        return normalizer.normalize(query)
    else:
        for p in prefix:
            norm_prefix, identifier, name = ground(p, query)
            if norm_prefix and identifier and name:
                return norm_prefix, identifier, name
        return None, None, query


class OboNormalizer(Normalizer):
    """A utility for normalizing by names."""

    def __init__(self, prefix: str) -> None:
        """Initialize the normalizer by an ontology's Bioregistry prefix."""
        self.prefix = prefix
        self._len_prefix = len(prefix)
        id_to_name = names.get_id_name_mapping(prefix)
        id_to_synonyms = names.get_id_synonyms_mapping(prefix)
        super().__init__(
            id_to_name=dict(id_to_name),
            id_to_synonyms=dict(id_to_synonyms),
            remove_prefix=prefix,
        )

    def __repr__(self) -> str:
        return f'OboNormalizer(prefix="{self.prefix}")'

    def normalize(self, query: str) -> NormalizationResult:
        """Try and normalize a name to a identifier and canonical name."""
        names = self.get_names(query)
        if not names:
            return None, None, query

        for name in names:
            identifiers = self.synonym_to_identifiers_mapping[name]
            for identifier in identifiers:
                if identifier in self.id_to_name:
                    return self.prefix, identifier, self.id_to_name[identifier]
            logger.warning(f"Could not find valid identifier for {name} from {identifiers}")

        # maybe it happens that one can't be found?
        logger.warning(f"was able to look up name {query}->{names} but not find fresh identifier")
        return None, None, query


@dataclass
class MultiNormalizer:
    """Multiple normalizers together.

    If you're looking for taxa of exotic plants, you might use:

    >>> from pyobo.normalizer import MultiNormalizer
    >>> normalizer = MultiNormalizer(prefixes=["ncbitaxon", "itis"])
    >>> normalizer.normalize("Homo sapiens")
    ('ncbitaxon', '9606', 'Homo sapiens')
    >>> normalizer.normalize("Abies bifolia")  # variety not listed in NCBI
    ('itis', '507501', 'Abies bifolia')
    >>> normalizer.normalize("vulcan")  # nice try, nerds
    (None, None, None)
    """

    #: The normalizers for each prefix
    normalizers: list[Normalizer]

    @staticmethod
    def from_prefixes(prefixes: list[str]) -> "MultiNormalizer":
        """Instantiate normalizers based on the given prefixes, in preferred order.."""
        return MultiNormalizer([get_normalizer(prefix) for prefix in prefixes])

    def normalize(self, query: str) -> NormalizationResult:
        """Try and normalize a canonical name using multiple normalizers."""
        for normalizer in self.normalizers:
            prefix, identifier, name = normalizer.normalize(query)
            if prefix and identifier and name:  # all not empty
                return prefix, identifier, name
        return None, None, query


# See: https://en.wikipedia.org/wiki/Dash
FIGURE_DASH = b"\xe2\x80\x92".decode("utf-8")
EN_DASH = b"\xe2\x80\x93".decode("utf-8")
EM_DASH = b"\xe2\x80\x94".decode("utf-8")
HORIZONAL_BAR = b"\xe2\x80\x95".decode("utf-8")
NORMAL_DASH = "-"


def normalize_dashes(s: str) -> str:
    """Normalize dashes in a string."""
    return (
        s.replace(FIGURE_DASH, NORMAL_DASH)
        .replace(EN_DASH, NORMAL_DASH)
        .replace(EM_DASH, NORMAL_DASH)
        .replace(HORIZONAL_BAR, NORMAL_DASH)
    )
