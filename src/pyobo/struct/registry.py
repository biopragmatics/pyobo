# -*- coding: utf-8 -*-

"""Data structures for registries."""

from dataclasses import dataclass

__all__ = [
    "Registry",
    "miriam",
    "ols",
    "obofoundry",
]


@dataclass
class Registry:
    """Represents a place to look up namespaces."""

    #: The name of the registry
    name: str

    #: The url that can be used to look up a resource.
    resolution_url: str

    def resolve_resource(self, resource: str) -> str:
        """Get the URl for the given resource."""
        return self.resolution_url + resource


miriam = Registry(
    name="miriam",
    resolution_url="https://registry.identifiers.org/registry/",
)

ols = Registry(
    name="ols",
    resolution_url="https://www.ebi.ac.uk/ols/ontologies/",
)

obofoundry = Registry(
    name="obofoundry",
    resolution_url="http://www.obofoundry.org/ontology/",
)
