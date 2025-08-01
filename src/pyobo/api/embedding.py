"""Embeddings for entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import curies
import numpy as np

from pyobo.api.names import get_definition, get_name

if TYPE_CHECKING:
    import sentence_transformers

__all__ = [
    "get_text_embedding",
]


def _get_transformer() -> sentence_transformers.SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model


def _get_text(
    reference: str | curies.Reference | curies.ReferenceTuple,
) -> str | None:
    name = get_name(reference)
    if name is None:
        return None
    description = get_definition(reference)
    if description:
        name += " " + description
    return name


def get_text_embedding(
    references: str | curies.Reference | curies.ReferenceTuple,
) -> np.ndarray | None:
    """Get a text embedding for an entity, or return none if no text is available.

    :param references: A reference, either as a string or Reference object
    :return: A 1D numpy float array of embeddings from :class:`sentence_transformers`
    """
    text = _get_text(references)
    if text is None:
        return None

    t = _get_transformer()
    res = t.encode([text])
    return res[0]


if __name__ == "__main__":
    get_text_embedding("GO:0000001")
