# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .registry import Registry, miriam
from .utils import obo_escape
from ..identifier_utils import normalize_curie

__all__ = [
    'Reference',
    'Referenced',
]


@dataclass
class Reference:
    """A namespace, identifier, and label."""

    #: The namespace's keyword
    prefix: str

    #: The entity's identifier in the namespace
    identifier: str

    name: Optional[str] = field(default=None, repr=None)

    #: The namespace's identifier in the registry
    registry_id: Optional[str] = field(default=None, repr=False)

    #: The registry in which the namespace can be looked up
    registry: Registry = field(default=miriam, repr=False)

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this reference."""
        return f'{self.prefix}:{self.identifier}'

    @staticmethod
    def from_curie(curie: str, name: Optional[str] = None) -> Reference:
        """Get a reference from a CURIE."""
        prefix, identifier = normalize_curie(curie)
        return Reference(prefix=prefix, identifier=identifier, name=name)

    @staticmethod
    def from_curies(curies: str) -> List[Reference]:
        """Get a list of references from a string with comma separated CURIEs."""
        return [
            Reference.from_curie(curie)
            for curie in curies.split(',')
            if curie.strip()
        ]

    @staticmethod
    def default(identifier, name) -> Reference:
        """Return a reference from the PyOBO namespace."""
        return Reference(prefix='obo', identifier=identifier, name=name)

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def __str__(self):  # noqa: D105
        if self.identifier.lower().startswith(f'{self.prefix.lower()}:'):
            rv = self.identifier.lower()
        else:
            rv = f'{self.prefix}:{self._escaped_identifier}'
        if self.name:
            rv = f'{rv} ! {self.name}'
        return rv

    def __hash__(self):  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))


class Referenced:
    """A class that contains a reference."""

    reference: Reference

    @property
    def prefix(self):  # noqa: D401
        """The prefix of the typedef."""
        return self.reference.prefix

    @property
    def name(self):  # noqa: D401
        """The name of the typedef."""
        return self.reference.name

    @property
    def identifier(self) -> str:  # noqa: D401
        """The local unique identifier for this typedef."""
        return self.reference.identifier

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this typedef."""
        return self.reference.curie
