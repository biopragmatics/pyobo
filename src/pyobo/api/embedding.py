"""Embeddings for entities."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import bioregistry
import curies
import numpy as np
import pandas as pd
from tqdm import tqdm
from typing_extensions import Unpack

from pyobo.api.edges import get_edges_df
from pyobo.api.names import get_definition, get_id_name_mapping, get_name
from pyobo.api.utils import get_version_from_kwargs
from pyobo.constants import GetOntologyKwargs, check_should_force
from pyobo.identifier_utils import wrap_norm_prefix
from pyobo.utils.path import CacheArtifact, get_cache_path

if TYPE_CHECKING:
    import sentence_transformers

__all__ = [
    "get_graph_embeddings_df",
    "get_text_embedding",
    "get_text_embedding_model",
    "get_text_embedding_similarity",
    "get_text_embeddings_df",
]


def get_text_embedding_model() -> sentence_transformers.SentenceTransformer:
    """Get the default text embedding model."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model


def _get_text(
    reference: str | curies.Reference | curies.ReferenceTuple,
    /,
    *,
    name: str | None = None,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    if name is None:
        name = get_name(reference, **kwargs)
    if name is None:
        return None
    description = get_definition(reference, **kwargs)
    if description:
        name += " " + description
    return name


def get_graph_embeddings_df(
    prefix: str,
    *,
    method: Literal["pykeen", "grape"] | None = None,
    epochs: int = 30,
    dimension: int = 32,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    """Get graph machine learning embeddings."""
    if method == "pykeen" or method is None:
        from pykeen.models import PairRE
        from pykeen.training import SLCWATrainingLoop
        from pykeen.triples import TriplesFactory
        from torch.optim import Adam

        triples_df = get_edges_df(prefix, **kwargs)
        training = TriplesFactory.from_labeled_triples(triples_df.values)
        model = PairRE(triples_factory=training, embedding_dim=dimension)
        optimizer = Adam(params=model.get_grad_params())
        training_loop = SLCWATrainingLoop(
            model=model, triples_factory=training, optimizer=optimizer
        )
        # can also set batch size here
        training_loop.train(triples_factory=training, num_epochs=epochs)
        embeddings = model.entity_representations[0]()
        df = pd.DataFrame(
            embeddings.detach().numpy(),
            index=[training.entity_id_to_label[i] for i in range(embeddings.shape[0])],
        )

    elif method == "grape":
        from ensmallen import Graph

        edges_df = get_edges_df(prefix, **kwargs)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).joinpath("test.tsv")
            edges_df[[":START_ID", ":END_ID"]].to_csv(path, header=None, sep="\t", index=False)
            graph = Graph.from_csv(
                edge_path=str(path),
                edge_list_separator="\t",
                sources_column_number=0,
                destinations_column_number=1,
                edge_list_numeric_node_ids=False,
                directed=True,
                name=bioregistry.get_name(prefix, strict=True),
                verbose=True,
            )
        graph = graph.remove_disconnected_nodes()

        from embiggen.embedders.ensmallen_embedders.second_order_line import (
            SecondOrderLINEEnsmallen,
        )

        embedding = SecondOrderLINEEnsmallen(embedding_size=dimension, epochs=epochs).fit_transform(
            graph
        )
        df = embedding.get_all_node_embedding()[0].sort_index()
        # df.columns = [str(c) for c in df.columns]
    else:
        raise ValueError(f"invalid graph machine learning method: {method}")

    df.index.name = "curie"
    return df


@wrap_norm_prefix
def get_text_embeddings_df(
    prefix: str,
    *,
    model: sentence_transformers.SentenceTransformer | None = None,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    """Get embeddings for all entities in the resource.

    :param prefix: A reference, either as a string or Reference object
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not
        given.
    :param kwargs: The keyword arguments to forward to ontology getter functions for
        names, definitions, and version

    :returns: A pandas dataframe with an index representing local unique identifiers and
        columns for the values of the model returned vectors
    """
    path = get_cache_path(
        prefix, CacheArtifact.embeddings, version=get_version_from_kwargs(prefix, kwargs)
    )
    if path.is_file() and not check_should_force(kwargs):
        df = pd.read_csv(path, sep="\t").set_index(0)
        return df

    id_to_name = get_id_name_mapping(prefix, **kwargs)

    luids, texts = [], []
    for identifier, name in tqdm(id_to_name.items(), desc=f"[{prefix}] constructing text"):
        text = _get_text(curies.ReferenceTuple(prefix, identifier), name=name, **kwargs)
        if text is None:
            continue
        luids.append(identifier)
        texts.append(text)
    if model is None:
        model = get_text_embedding_model()
    res = model.encode(texts, show_progress_bar=True)
    df = pd.DataFrame(res, index=luids)
    df.to_csv(path, sep="\t")  # index is important here!
    return df


def get_text_embedding(
    reference: str | curies.Reference | curies.ReferenceTuple,
    *,
    model: sentence_transformers.SentenceTransformer | None = None,
) -> np.ndarray | None:
    """Get a text embedding for an entity, or return none if no text is available.

    :param reference: A reference, either as a string or Reference object
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not
        given.

    :returns: A 1D numpy float array of embeddings from :class:`sentence_transformers`

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
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not
        given.

    :returns: A floating point similarity, if text is available for both references,
        otherwise none

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
