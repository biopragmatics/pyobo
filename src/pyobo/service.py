"""An abstraction over lookup services.

This accomplishes something similar to the
TS4NFDI, but accessible through a programmatic
API instead of being tied up within a web-based
frontend framework.
"""

from __future__ import annotations

import unittest
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated

from curies import Reference
from pydantic import BaseModel
from starlette.testclient import TestClient

import pyobo

if TYPE_CHECKING:
    import fastapi
    import ols_client
    import ontoportal_client


class LabelResult(BaseModel):
    """A result for a label."""

    reference: Reference
    label: str


class Service(ABC):
    """An abstraction over a lookup service."""

    @abstractmethod
    def get_label(self, reference: Reference, *, language: str | None = None) -> LabelResult | None:
        """Get the label for the entity."""


class OntologyLookupService(Service):
    """A wrapper around an ontology lookup service instance."""

    client: ols_client.Client


class OntoportalService(Service):
    """A wrapper around an OntoPortal instance."""

    client: ontoportal_client.OntoPortalClient


class WikidataService(Service):
    """A wrapper around a Wikibase."""


class PyOBOService(Service):
    """A wrapper around a PyOBO in-memory service."""

    def get_label(self, reference: Reference, *, language: str | None = None) -> LabelResult | None:
        """Get a label via PyOBO."""
        if label := pyobo.get_name(reference):
            return LabelResult(reference=reference, label=label)
        return None


class CascadingService(Service):
    """A lookup that cascades."""

    def __init__(self, lookups: list[CascadingService]) -> None:
        """Initialize the service."""
        self.lookups = lookups

    def get_label(self, reference: Reference, *, language: str | None = None) -> LabelResult | None:
        """Get the label."""
        for service in self.lookups:
            if rv := service.get_label(reference):
                return rv
        return None


def _get_service(request: fastapi.Request) -> Service:
    return request.app.service  # type:ignore


def get_route() -> fastapi.APIRouter:
    """Get a FastAPI router for the lookup service."""
    from fastapi import APIRouter, Depends, HTTPException

    router = APIRouter()

    @router.get("/{curie}/label")
    def get_label(s: Annotated[Service, Depends(_get_service)], curie: str) -> LabelResult | None:
        """Get the label for an entity by CURIE."""
        reference = Reference.from_curie(curie)
        if label := s.get_label(reference):
            return label
        raise HTTPException(status_code=404, detail=f"label not found for {reference.curie}")

    return router


class MockService(Service):
    """A mock lookup."""

    def __init__(self, labels: dict[Reference, str]) -> None:
        """Initialize the service with dictionaries."""
        self.labels = labels

    def get_label(self, reference: Reference, *, language: str | None = None) -> LabelResult | None:
        """Get the label for the entity from a dictionary."""
        if label := self.labels.get(reference):
            return LabelResult(reference=reference, label=label)
        return None


class TestRouter(unittest.TestCase):
    """A test case for web API."""

    def setUp(self) -> None:
        """Set up a router with a mock lookup."""
        from fastapi import FastAPI

        self.app = FastAPI()
        self.app.service = MockService(labels={Reference.from_curie("a:1"): "label 1"})  # type:ignore[attr-defined]
        self.app.mount("/", get_route())
        self.test_client = TestClient(self.app)

    def test_label(self) -> None:
        """Test getting the label."""
        res = self.test_client.get("/a:1/label")
        self.assertEqual(res.status_code, 200, msg=res.text)
        self.assertEqual(
            {"reference": {"prefix": "a", "identifier": "1"}, "label": "label 1"}, res.json()
        )
