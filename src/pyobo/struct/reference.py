# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

import bioregistry

from .utils import obo_escape
from ..constants import DEFAULT_PATTERN, DEFAULT_PREFIX
from ..identifier_utils import normalize_curie

__all__ = [
    "Reference",
    "Referenced",
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

    @classmethod
    def auto(cls, prefix: str, identifier: str) -> "Reference":
        """Create a reference and auto-populate its name."""
        from ..api import get_name

        name = get_name(prefix, identifier)
        return cls(prefix=prefix, identifier=identifier, name=name)

    @property
    def curie(self) -> str:
        """The CURIE for this reference."""  # noqa: D401
        return f"{self.prefix}:{self.identifier}"

    @property
    def link(self) -> Optional[str]:
        """Get a link for this term."""
        return bioregistry.get_iri(self.prefix, self.identifier)

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return f"https://bioregistry.io/{self.curie}"

    @property
    def pair(self) -> Tuple[str, str]:
        """The pair of namespace/identifier."""  # noqa: D401
        return self.prefix, self.identifier

    @staticmethod
    def from_curie(
        curie: str,
        name: Optional[str] = None,
        *,
        strict: bool = True,
        auto: bool = False,
    ) -> Optional["Reference"]:
        """Get a reference from a CURIE.

        :param curie: The compact URI (CURIE) to parse in the form of `<prefix>:<identifier>`
        :param name: The name associated with the CURIE
        :param strict: If true, raises an error if the CURIE can not be parsed.
        :param auto: Automatically look up name
        """
        prefix, identifier = normalize_curie(curie, strict=strict)
        if prefix is None or identifier is None:
            return None
        if name is None and auto:
            return Reference.auto(prefix=prefix, identifier=identifier)
        return Reference(prefix=prefix, identifier=identifier, name=name)

    @staticmethod
    def default(identifier: str, name: Optional[str] = None) -> "Reference":
        """Return a reference from the PyOBO namespace."""
        if not DEFAULT_PATTERN.match(identifier):
            raise ValueError(f"identifier is invalid: {identifier}")
        return Reference(prefix=DEFAULT_PREFIX, identifier=identifier, name=name)

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def to_dict(self) -> Mapping[str, str]:
        """Return the reference as a dictionary."""
        rv = {
            "prefix": self.prefix,
            "identifier": self.identifier,
        }
        if self.name:
            rv["name"] = self.name
        return rv

    def get_url(self) -> Optional[str]:
        """Return a URL for this reference, if possible."""
        return bioregistry.get_iri(self.prefix, self.identifier)

    def __str__(self):  # noqa: D105
        identifier_lower = self.identifier.lower()
        if identifier_lower.startswith(f"{self.prefix.lower()}:"):
            rv = identifier_lower
        else:
            rv = f"{self.prefix}:{self._escaped_identifier}"
        if self.name:
            rv = f"{rv} ! {self.name}"
        return rv

    def __hash__(self):  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))


class Referenced:
    """A class that contains a reference."""

    reference: Reference

    @property
    def prefix(self):
        """The prefix of the typedef."""  # noqa: D401
        return self.reference.prefix

    @property
    def name(self):
        """The name of the typedef."""  # noqa: D401
        return self.reference.name

    @property
    def identifier(self) -> str:
        """The local unique identifier for this typedef."""  # noqa: D401
        return self.reference.identifier

    @property
    def curie(self) -> str:
        """The CURIE for this typedef."""  # noqa: D401
        return self.reference.curie

    @property
    def pair(self) -> Tuple[str, str]:
        """The pair of namespace/identifier."""  # noqa: D401
        return self.reference.pair

    @property
    def link(self) -> Optional[str]:
        """Get the link to the reference."""
        return self.reference.link

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return self.reference.bioregistry_link
