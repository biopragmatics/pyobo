"""Wrapper around scispacy.

New, :class:`KnowledgeBase` subclasses can be defined based on :mod:`pyobo` (after
running ``pip install pyobo``) like in the following:

.. code-block:: python

    import pyobo
    from scispacy.linking_utils import KnowledgeBase, entities_from_pyobo


    class PlantTraitOntology(KnowledgeBase):
        def __init__(self) -> None:
            # see https://bioregistry.io/registry/to
            super().__init__(pyobo.get_scispacy_entities("to"))


    kb = PlantTraitOntology()

New _ad-hoc_ :class:`KnowledgeBase` instances can be constructed using :mod:`pyobo` like
in the following, using the `Plant Trait Ontology <https://bioregistry.io/to>`_ as an
example:

.. code-block:: python

    import pyobo

    kb = pyobo.get_scispacy_knowledgebase("to")

You can go further and create a linker using the following:

.. code-block:: python

    import pyobo
    import spacy
    from scispacy.linking import EntityLinker

    kb = pyobo.get_scispacy_knowledgebase("to")
    linker = EntityLinker.from_kb(kb, filter_for_definitions=False)

This can be wrapped with :func:`pyobo.get_scispacy_entity_linker` like in, then put
together with spacy to annotate text

.. code-block:: python

    import pyobo
    import spacy
    from scispacy.linking import EntityLinker

    linker = pyobo.get_scispacy_entity_linker("to", filter_for_definitions=False)

    # now, put it all together with a NER model
    nlp = spacy.load("en_core_web_sm")
    doc = linker(nlp(text))
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from typing_extensions import Unpack

from ..constants import GetOntologyKwargs
from ..getters import get_ontology
from ..utils.path import prefix_directory_join

if TYPE_CHECKING:
    from scispacy.linking import EntityLinker
    from scispacy.linking_utils import Entity, KnowledgeBase

__all__ = [
    "get_scispacy_entities",
    "get_scispacy_entity_linker",
    "get_scispacy_knowledgebase",
]


def get_scispacy_entity_linker(
    prefix: str,
    ontology_kwargs: GetOntologyKwargs | None = None,
    candidate_generator_kwargs: dict[str, Any] | None = None,
    entity_linker_kwargs: dict[str, Any] | None = None,
) -> EntityLinker:
    """Get a knowledgebase object for usage with :mod:`scispacy`."""
    from scispacy.linking import EntityLinker

    kb = get_scispacy_knowledgebase(prefix, **(ontology_kwargs or {}))
    # TODO extract version from kwargs to pass to prefix_directory_join
    cache_directory = prefix_directory_join(prefix, "scispacy")
    linker = EntityLinker.from_kb(
        kb,
        ann_index_out_dir=cache_directory.as_posix(),
        candidate_generator_kwargs=candidate_generator_kwargs,
        **(entity_linker_kwargs or {}),
    )
    return linker


def get_scispacy_knowledgebase(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> KnowledgeBase:
    """Get a knowledgebase object for usage with :mod:`scispacy`."""
    from scispacy.linking_utils import KnowledgeBase

    return KnowledgeBase(get_scispacy_entities(prefix, **kwargs))


def get_scispacy_entities(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> Iterable[Entity]:
    """Iterate over entities in a given ontology via :mod:`pyobo`.

    :param prefix :
        The ontology's prefix, such as ``go` for Gene Ontology, ``doid`` for the Disease
        Ontology, or more.

    :param kwargs :
        keyword arguments to pass to :func:`pyobo.get_ontology`, such as ``version``.

    :yields: Entity objects for all terms in the ontology
    """
    from scispacy.linking_utils import Entity

    ontology = get_ontology(prefix, **kwargs)
    for term in ontology:
        yield Entity(
            concept_id=term.curie,
            canonical_name=term.name,
            aliases=[s.name for s in term.synonyms],
            definition=term.definition,
        )
