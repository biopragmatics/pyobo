"""A temporary place for the Reference class until it's upstreamed."""

from __future__ import annotations

import bioregistry
import curies
from curies.api import ExpansionError
from pydantic import model_validator

from .constants import GLOBAL_CHECK_IDS

__all__ = [
    "Reference",
]


class Reference(curies.NamableReference):
    """A namespace, identifier, and label."""

    @model_validator(mode="before")
    def validate_identifier(cls, values):  # noqa
        """Validate the identifier."""
        prefix, identifier = values.get("prefix"), values.get("identifier")
        if not prefix or not identifier:
            return values
        resource = bioregistry.get_resource(prefix)
        if resource is None:
            raise ExpansionError(f"Unknown prefix: {prefix}")
        values["prefix"] = resource.prefix
        if " " in identifier:
            raise ValueError(f"[{prefix}] space in identifier: {identifier}")
        values["identifier"] = resource.standardize_identifier(identifier)
        if GLOBAL_CHECK_IDS and not resource.is_valid_identifier(values["identifier"]):
            raise ValueError(f"non-standard identifier: {resource.prefix}:{values['identifier']}")
        return values
