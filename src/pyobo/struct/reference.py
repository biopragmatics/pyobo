# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from dataclasses import dataclass, field
from typing import Mapping, Optional

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

    name: Optional[str] = field(default=None)

    #: The namespace's identifier in the registry
    registry_id: Optional[str] = field(default=None, repr=False)

    #: The registry in which the namespace can be looked up
    registry: Registry = field(default=miriam, repr=False)

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this reference."""
        return f'{self.prefix}:{self.identifier}'

    @staticmethod
    def from_curie(curie: str, name: Optional[str] = None) -> Optional['Reference']:
        """Get a reference from a CURIE.

        :param curie: The compact URI (CURIE) to parse in the form of `<prefix>:<identifier>`
        :param name: The name associated with the CURIE
        """
        prefix, identifier = normalize_curie(curie)
        if prefix is None and identifier is None:
            return
        return Reference(prefix=prefix, identifier=identifier, name=name)

    @staticmethod
    def default(identifier: str, name: Optional[str] = None) -> 'Reference':
        """Return a reference from the PyOBO namespace."""
        return Reference(prefix='obo', identifier=identifier, name=name)

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def to_dict(self) -> Mapping[str, str]:
        """Return the reference as a dictionary."""
        rv = {
            'prefix': self.prefix,
            'identifier': self.identifier,
        }
        if self.name:
            rv['name'] = self.name
        return rv

    def __str__(self):  # noqa: D105
        identifier_lower = self.identifier.lower()
        if identifier_lower.startswith(f'{self.prefix.lower()}:'):
            rv = identifier_lower
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
