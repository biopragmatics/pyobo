"""Reusable configuration."""

from pydantic import BaseModel, Field


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


class Rules(BaseModel):
    """A model for blacklists and rewrites."""

    blacklists: Blacklist
    rewrites: Rewrites

    def preprocess(self, s: str) -> str | None:
        """Pre-process a string, returning none if hitting a blacklist."""
