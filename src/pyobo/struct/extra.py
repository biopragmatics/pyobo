# -*- coding: utf-8 -*-

"""Synonym structures."""

from dataclasses import dataclass, field
from typing import List, Optional

from .reference import Reference
from .utils import comma_separate

__all__ = [
    "Synonym",
    "SynonymTypeDef",
]


@dataclass
class SynonymTypeDef:
    """A type definition for synonyms in OBO."""

    id: str
    name: str

    def to_obo(self) -> str:
        """Serialize to OBO."""
        return f'synonymtypedef: {self.id} "{self.name}"'

    @classmethod
    def from_text(cls, text) -> "SynonymTypeDef":
        """Get a type definition from text that's normalized."""
        return cls(
            id=text.lower()
                .replace("-", "_")
                .replace(" ", "_")
                .replace('"', "")
                .replace(")", "")
                .replace("(", ""),
            name=text.replace('"', ""),
        )


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: str = "EXACT"

    #: The type of synonym. Must be defined in OBO document!
    type: Optional[SynonymTypeDef] = None

    #: References to articles where the synonym appears
    provenance: List[Reference] = field(default_factory=list)

    def to_obo(self) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f"synonym: {self._fp()}"

    def _fp(self) -> str:
        x = f'"{self._escape(self.name)}" {self.specificity}'
        if self.type:
            x = f"{x} {self.type.id}"
        return f"{x} [{comma_separate(self.provenance)}]"

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace('"', '\\"')
