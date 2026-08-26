"""Embeddings for entities."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, Union, cast

import bioregistry
import curies
import numpy as np
import pandas as pd
from pystow import get_sentence_transformer
from tqdm.contrib.concurrent import process_map
from typing_extensions import Unpack

from pyobo.api.edges import get_edges_df
from pyobo.api.names import get_definition, get_id_definition_mapping, get_id_name_mapping, get_name
from pyobo.api.utils import get_version_from_kwargs
from pyobo.constants import GetOntologyKwargs, check_should_force
from pyobo.identifier_utils import wrap_norm_prefix
from pyobo.utils.path import CacheArtifact, get_cache_path

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

__all__ = [
    "get_graph_embeddings_df",
    "get_text_embedding",
    "get_text_embedding_similarity",
    "get_text_embeddings_df",
]


def _get_text(
    reference: str | curies.Reference | curies.ReferenceTuple,
    /,
    *,
    name: str | None = None,
) -> str | None:
    if name is None:
        name = get_name(reference)
    if name is None:
        return None
    description = get_definition(reference)
    if description:
        name += " " + description
    # TODO include synonyms?
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


EMBEDDING_INDEX_NAME = "luid"
EMBEDDING_DIMENSIONALITY = 384
TransformerHint: TypeAlias = Union[str, "SentenceTransformer", None]


@wrap_norm_prefix
def get_text_embeddings_df(
    prefix: str,
    *,
    model: TransformerHint = None,
    encode_kwargs: dict[str, Any] | None = None,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    """Get embeddings for all entities in the resource.

    :param prefix: A reference, either as a string or Reference object
    :param model: A sentence transformer model. Defaults to ``all-MiniLM-L6-v2`` if not
        given.
    :param encode_kwargs: Additional keyword arguments to pass to the encoder function
        :meth:`sentence_transformers.SentenceTransformer.encode`
    :param kwargs: The keyword arguments to forward to ontology getter functions for
        names, definitions, and version

    :returns: A pandas dataframe with an index representing local unique identifiers and
        columns for the values of the model returned vectors
    """
    path = get_cache_path(
        prefix, CacheArtifact.embeddings, version=get_version_from_kwargs(prefix, kwargs)
    )
    if path.is_file() and not check_should_force(kwargs):
        # make an explicit dictionary so we make sure that the index column
        # doesn't also get interpreted as a float. This would silently be an
        # issue for any identifier space that has number-looking identifier patterns
        dtype: dict[str, Any] = {str(i): float for i in range(EMBEDDING_DIMENSIONALITY)}
        dtype[EMBEDDING_INDEX_NAME] = str
        df = pd.read_csv(path, sep="\t", dtype=dtype, index_col=0)
        if df.index.name != EMBEDDING_INDEX_NAME:
            df.index.name = EMBEDDING_INDEX_NAME
        df.index = df.index.astype(str)
        return df

    id_to_name = get_id_name_mapping(prefix, **kwargs)
    # no kwargs needed because ontology was loaded above.
    id_to_description = get_id_definition_mapping(prefix)

    identifiers = list(id_to_name)
    texts = process_map(
        partial(_id_to_text, id_to_name=id_to_name, id_to_description=id_to_description),
        identifiers,
        desc=f"[{prefix}] constructing text",
        unit_scale=True,
        chunksize=1000,
    )

    model_ = get_sentence_transformer(model)
    # TODO update to using MPL
    if encode_kwargs is None:
        encode_kwargs = {}
    encode_kwargs.setdefault("show_progress_bar", True)
    res = model_.encode(texts, **encode_kwargs)
    df = pd.DataFrame(res, index=identifiers)
    df.index.name = EMBEDDING_INDEX_NAME
    df.to_csv(path, sep="\t")  # index is important here!
    return df


def _id_to_text(
    identifier: str, id_to_name: Mapping[str, str], id_to_description: Mapping[str, str]
) -> str:
    if identifier in id_to_description:
        return id_to_name[identifier] + " " + id_to_description[identifier]
    return id_to_name[identifier]


def get_text_embedding(
    reference: str | curies.Reference | curies.ReferenceTuple,
    *,
    model: TransformerHint = None,
) -> np.ndarray[tuple[int], np.dtype[np.float64]] | None:
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
        from pystow import get_sentence_transformer

        model = get_sentence_transformer()
        embedding = pyobo.get_text_embedding("GO:0000001", model=model)
        # [-5.68335280e-02  7.96175096e-03 -3.36112119e-02  2.34440481e-03 ... ]
    """
    text = _get_text(reference)
    if text is None:
        return None
    model_ = get_sentence_transformer(model)
    res = model_.encode([text])
    return cast(np.ndarray[tuple[int], np.dtype[np.float64]], res[0])


def get_text_embedding_similarity(
    reference_1: str | curies.Reference | curies.ReferenceTuple,
    reference_2: str | curies.Reference | curies.ReferenceTuple,
    *,
    model: TransformerHint = None,
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
        from pystow import get_sentence_transformer

        model = get_sentence_transformer()
        similarity = pyobo.get_text_embedding_similarity("GO:0000001", "GO:0000004", model=model)
        # 0.24702128767967224
    """
    model_ = get_sentence_transformer(model)
    e1 = get_text_embedding(reference_1, model=model_)
    e2 = get_text_embedding(reference_2, model=model_)
    if e1 is None or e2 is None:
        return None
    return cast(float, model_.similarity(e1, e2)[0][0].item())
