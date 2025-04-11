"""Reusable configuration."""

from typing import TypeVar

import curies
from pydantic import BaseModel, Field

__all__ = ["Blacklist", "Rewrites", "Rules"]

X = TypeVar("X", bound=curies.Reference)


class Blacklist(BaseModel):
    """A model for prefix and full blacklists."""

    full: list[str]
    resource_full: dict[str, list[str]]
    prefix: list[str]
    resource_prefix: dict[str, list[str]]
    suffix: list[str]

    def _sort(self) -> None:
        self.full.sort()
        self.prefix.sort()
        self.suffix.sort()
        for v in self.resource_full.values():
            v.sort()
        for v in self.resource_prefix.values():
            v.sort()

    def str_has_blacklisted_prefix(
        self, str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
    ) -> bool:
        """Check if the CURIE string has a blacklisted prefix."""
        if ontology_prefix:
            prefixes: list[str] = self.resource_prefix.get(ontology_prefix, [])
            if prefixes and any(str_or_curie_or_uri.startswith(prefix) for prefix in prefixes):
                return True
        return any(str_or_curie_or_uri.startswith(prefix) for prefix in self.prefix)

    def str_has_blacklisted_suffix(self, str_or_curie_or_uri: str) -> bool:
        """Check if the CURIE string has a blacklisted suffix."""
        return any(str_or_curie_or_uri.endswith(suffix) for suffix in self.suffix)

    def str_is_blacklisted_full(
        self, str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
    ) -> bool:
        """Check if the full CURIE string is blacklisted."""
        if ontology_prefix and str_or_curie_or_uri in self.resource_full.get(
            ontology_prefix, set()
        ):
            return True
        return str_or_curie_or_uri in self.full


class Rewrites(BaseModel):
    """A model for prefix and full rewrites."""

    full: dict[str, str] = Field(..., description="Global remappings for an entire string")
    resource_full: dict[str, dict[str, str]] = Field(
        ..., description="Resource-keyed remappings for an entire string"
    )
    prefix: dict[str, str] = Field(..., description="Global remappings of just the prefix")
    resource_prefix: dict[str, dict[str, str]] = Field(
        ..., description="Resource-keyed remappings for just a prefix"
    )

    def remap_full(
        self, str_or_curie_or_uri: str, cls: type[X], *, ontology_prefix: str | None = None
    ) -> X | None:
        """Remap the string if possible otherwise return it."""
        if ontology_prefix:
            resource_rewrites: dict[str, str] = self.resource_full.get(ontology_prefix, {})
            if resource_rewrites and str_or_curie_or_uri in resource_rewrites:
                return cls.from_curie(resource_rewrites[str_or_curie_or_uri])

        if str_or_curie_or_uri in self.full:
            return cls.from_curie(self.full[str_or_curie_or_uri])

        return None

    def remap_prefix(self, str_or_curie_or_uri: str, ontology_prefix: str | None = None) -> str:
        """Remap a prefix."""
        if ontology_prefix is not None:
            for old_prefix, new_prefix in self.resource_prefix.get(ontology_prefix, {}).items():
                if str_or_curie_or_uri.startswith(old_prefix):
                    return new_prefix + str_or_curie_or_uri[len(old_prefix) :]
        for old_prefix, new_prefix in self.prefix.items():
            if str_or_curie_or_uri.startswith(old_prefix):
                return new_prefix + str_or_curie_or_uri[len(old_prefix) :]
        return str_or_curie_or_uri


class Rules(BaseModel):
    """A model for blacklists and rewrites."""

    blacklists: Blacklist
    rewrites: Rewrites

    def str_has_blacklisted_prefix(
        self, str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
    ) -> bool:
        """Check if the CURIE string has a blacklisted prefix."""
        return self.blacklists.str_has_blacklisted_prefix(
            str_or_curie_or_uri, ontology_prefix=ontology_prefix
        )

    def str_has_blacklisted_suffix(self, str_or_curie_or_uri: str) -> bool:
        """Check if the CURIE string has a blacklisted suffix."""
        return self.blacklists.str_has_blacklisted_suffix(str_or_curie_or_uri)

    def str_is_blacklisted_full(
        self, str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
    ) -> bool:
        """Check if the full CURIE string is blacklisted."""
        return self.blacklists.str_is_blacklisted_full(
            str_or_curie_or_uri, ontology_prefix=ontology_prefix
        )

    def remap_full(
        self, str_or_curie_or_uri: str, cls: type[X], *, ontology_prefix: str | None = None
    ) -> X | None:
        """Remap the string if possible otherwise return it."""
        return self.rewrites.remap_full(
            str_or_curie_or_uri, cls=cls, ontology_prefix=ontology_prefix
        )

    def remap_prefix(self, str_or_curie_or_uri: str, ontology_prefix: str | None = None) -> str:
        """Remap a prefix."""
        return self.rewrites.remap_prefix(str_or_curie_or_uri, ontology_prefix=ontology_prefix)
