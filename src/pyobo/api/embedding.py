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
    "get_text_embedding_model",
    "get_text_embedding_similarity",
]


def get_text_embedding_model() -> sentence_transformers.SentenceTransformer:
    """Get the default text embedding model."""
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
    reference: str | curies.Reference | curies.ReferenceTuple,
    *,
    model: sentence_transformers.SentenceTransformer | None = None,
) -> np.ndarray | None:
    """Get a text embedding for an entity, or return none if no text is available.

    :param reference: A reference, either as a string or Reference object
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not given.
    :return: A 1D numpy float array of embeddings from :class:`sentence_transformers`

    .. code-block:: python

        import pyobo

        embedding = pyobo.get_text_embedding("GO:0000001")
        # [-5.68335280e-02  7.96175096e-03 -3.36112119e-02  2.34440481e-03 ... ]

    If you want to do multiple operations, load up the model for reuse

    .. code-block:: python

        import pyobo
        from pyobo.api.embedding import get_text_embedding_model

        model = get_text_embedding_model()
        embedding = pyobo.get_text_embedding("GO:0000001", model=model)
        # [-5.68335280e-02  7.96175096e-03 -3.36112119e-02  2.34440481e-03 ... ]
    """
    text = _get_text(reference)
    if text is None:
        return None
    if model is None:
        model = get_text_embedding_model()
    res = model.encode([text])
    return res[0]


def get_text_embedding_similarity(
    reference_1: str | curies.Reference | curies.ReferenceTuple,
    reference_2: str | curies.Reference | curies.ReferenceTuple,
    *,
    model: sentence_transformers.SentenceTransformer | None = None,
) -> float | None:
    """Get the pairwise similarity.

    :param reference_1: A reference, given as a string or Reference object
    :param reference_2: A second reference
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not given.
    :returns:
        A floating point similarity, if text is available for both references, otherwise none

    .. code-block:: python

        import pyobo

        similarity = pyobo.get_text_embedding_similarity("GO:0000001", "GO:0000004")
        # 0.24702128767967224

    If you want to do multiple operations, load up the model for reuse

    .. code-block:: python

        import pyobo
        from pyobo.api.embedding import get_text_embedding_model

        model = get_text_embedding_model()
        similarity = pyobo.get_text_embedding_similarity("GO:0000001", "GO:0000004", model=model)
        # 0.24702128767967224
    """
    if model is None:
        model = get_text_embedding_model()
    e1 = get_text_embedding(reference_1, model=model)
    e2 = get_text_embedding(reference_2, model=model)
    if e1 is None or e2 is None:
        return None
    return model.similarity(e1, e2)[0][0].item()
