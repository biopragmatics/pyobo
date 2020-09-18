# -*- coding: utf-8 -*-

"""Use synonyms from OBO to normalize names."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

from . import extract
from .identifier_utils import normalize_dashes, normalize_prefix
from .io_utils import multisetdict

__all__ = [
    'ground',
    'Normalizer',
    'OboNormalizer',
    'MultiNormalizer',
    'NormalizationResult',
]

logger = logging.getLogger(__name__)

NormalizationSuccess = Tuple[str, str, str]
NormalizationFailure = Tuple[None, None, str]
NormalizationResult = Union[NormalizationSuccess, NormalizationFailure]


class Normalizer(ABC):
    """A normalizer."""

    id_to_name: Dict[str, str]
    id_to_synonyms: Dict[str, List[str]]

    #: A mapping from all synonyms to the set of identifiers that they point to.
    #: In a perfect world, each would only be a single element.
    synonym_to_identifiers_mapping: Dict[str, Set[str]]
    #: A mapping from normalized names to the actual ones that they came from
    norm_name_to_name: Dict[str, Set[str]]

    def __init__(
        self,
        id_to_name: Dict[str, str],
        id_to_synonyms: Dict[str, List[str]],
        remove_prefix: Optional[str] = None,
    ) -> None:  # noqa: D107
        self.id_to_name = id_to_name
        self.id_to_synonyms = id_to_synonyms
        self.synonym_to_identifiers_mapping = multisetdict(self._iterate_synonyms_to_identifiers(
            id_to_name=self.id_to_name,
            id_to_synonyms=self.id_to_synonyms,
            remove_prefix=remove_prefix,
        ))
        self.norm_name_to_name = self._get_norm_name_to_names(self.synonym_to_identifiers_mapping)

    @classmethod
    def _get_norm_name_to_names(cls, synonyms: Iterable[str]) -> Mapping[str, Set[str]]:
        return multisetdict(
            (cls._normalize_text(synonym), synonym)
            for synonym in synonyms
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.strip().strip('"').strip("'").lower()
        text = normalize_dashes(text)
        text = text.replace('-', '')  # remove all dashes
        text = text.replace(' ', '')  # remove all spaces
        return text

    @staticmethod
    def _iterate_synonyms_to_identifiers(
        *,
        id_to_name: Mapping[str, str],
        id_to_synonyms: Mapping[str, Iterable[str]],
        remove_prefix: Optional[str] = None,
    ) -> Iterable[Tuple[str, str]]:
        if remove_prefix is not None:
            remove_prefix = f'{remove_prefix.lower().rstrip(":")}:'

        # Add name
        for identifier, name in id_to_name.items():
            if remove_prefix and identifier.lower().startswith(remove_prefix):
                identifier = identifier[len(remove_prefix):]

            yield name, identifier

        # Add synonyms
        for identifier, synonyms in id_to_synonyms.items():
            if remove_prefix and identifier.lower().startswith(remove_prefix):
                identifier = identifier[len(remove_prefix):]

            for synonym in synonyms:
                # it might overwrite but this is probably always due to alternate ids
                yield synonym, identifier

    def get_names(self, query: str) -> List[str]:
        """Get all names to which the query text maps."""
        norm_text = self._normalize_text(query)
        return list(self.norm_name_to_name.get(norm_text, []))

    @abstractmethod
    def normalize(self, query: str) -> NormalizationResult:
        """Try and normalize a name to a identifier and canonical name."""
        raise NotImplementedError


@lru_cache()
def get_normalizer(prefix: str) -> Normalizer:
    """Get an OBO normalizer."""
    norm_prefix = normalize_prefix(prefix)
    if norm_prefix is None:
        raise ValueError(f'unhandled prefix: {prefix}')
    logger.info('getting obo normalizer for %s', norm_prefix)
    normalizer = OboNormalizer(norm_prefix)
    logger.debug('normalizer for %s with %s name lookups', normalizer.prefix, len(normalizer.norm_name_to_name))
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

    def __init__(self, prefix: str) -> None:  # noqa: D107
        self.prefix = prefix
        self._len_prefix = len(prefix)
        id_to_name = extract.get_id_name_mapping(prefix)
        id_to_synonyms = extract.get_id_synonyms_mapping(prefix)
        super().__init__(
            id_to_name=dict(id_to_name),
            id_to_synonyms=dict(id_to_synonyms),
            remove_prefix=prefix,
        )

    def __repr__(self) -> str:  # noqa: D105
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
            logger.warning(f'Could not find valid identifier for {name} from {identifiers}')

        # maybe it happens that one can't be found?
        logger.warning(f'was able to look up name {query}->{names} but not find fresh identifier')
        return None, None, query


@dataclass
class MultiNormalizer:
    """Multiple normalizers together.

    If you're looking for taxa of exotic plants, you might use:

    >>> from pyobo.normalizer import MultiNormalizer
    >>> normalizer = MultiNormalizer(prefixes=['ncbitaxon', 'itis'])
    >>> normalizer.normalize('Homo sapiens')
    ('ncbitaxon', '9606', 'Homo sapiens')
    >>> normalizer.normalize('Abies bifolia')  # variety not listed in NCBI
    ('itis', '507501', 'Abies bifolia')
    >>> normalizer.normalize('vulcan')  # nice try, nerds
    (None, None, None)
    """

    #: The normalizers for each prefix
    normalizers: List[Normalizer]

    @staticmethod
    def from_prefixes(prefixes: List[str]) -> 'MultiNormalizer':
        """Instantiate normalizers based on the given prefixes, in preferred order.."""
        return MultiNormalizer([
            get_normalizer(prefix)
            for prefix in prefixes
        ])

    def normalize(self, query: str) -> NormalizationResult:
        """Try and normalize a canonical name using multiple normalizers."""
        for normalizer in self.normalizers:
            prefix, identifier, name = normalizer.normalize(query)
            if prefix and identifier and name:  # all not empty
                return prefix, identifier, name
        return None, None, query
