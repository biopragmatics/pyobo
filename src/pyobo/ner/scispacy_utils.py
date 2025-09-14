"""A bridge between PyOBO and :mod:`scispacy`.

:mod:`scispacy` implements a lexical index in
:class:`scispacy.linking_utils.KnowledgeBase` which keeps track of labels, synonyms, and
definitions for entities. These are used to construct a TF-IDF index and implement
entity linking (also called named entity normalization (NEN) or grounding) in
:class:`scispacy.linking.EntityLinker`.

Constructing a Lexical Index
============================

An *ad hoc* SciSpacy lexical index can be constructed on-the-fly by passing a
Bioregistry prefix to :func:`pyobo.get_scispacy_knowledgebase`. In the following
example, the prefix ``to`` is used to construct a lexical index for the `Plant Trait
Ontology <https://bioregistry.io/to>`_.

.. code-block:: python

    import pyobo
    from scispacy.linking_utils import KnowledgeBase

    kb: KnowledgeBase = pyobo.get_scispacy_knowledgebase("to")

The high-level PyOBO interface abstracts the differences between external ontologies
like the Plant Trait Ontology and databases that are converted to ontologies in
:mod:`pyobo.sources` like the `HUGO Gene Nomenclature Committee
<https://bioregistry.io/hgnc>`_. Therefore, you can also do

.. code-block:: python

    import pyobo
    from scispacy.linking_utils import KnowledgeBase

    kb: KnowledgeBase = pyobo.get_scispacy_knowledgebase("hgnc")

Alternatively, a reusable class can be defined like in the following:

.. code-block:: python

    import pyobo
    from scispacy.linking_utils import KnowledgeBase


    class HGNCKnowledgeBase(KnowledgeBase):
        def __init__(self) -> None:
            super().__init__(pyobo.get_scispacy_entities("hgnc"))


    kb = HGNCKnowledgeBase()

Constructing an Entity Linker
=============================

An entity linker can be constructed from a :class:`scispacy.linking_utils.KnowledgeBase`
like in:

.. code-block:: python

    import pyobo
    from scispacy.linking import EntityLinker

    kb = pyobo.get_scispacy_knowledgebase("hgnc")
    linker = EntityLinker.from_kb(kb, filter_for_definitions=False)

Where ``filter_for_definitions`` is set to ``False`` to retain entities that don't have
a definition.

PyOBO provides a convenience function :func:`pyobo.get_scispacy_entity_linker` that
wraps this workflow and also automatically caches the TF-IDF index constructed in the
process in the correctly versioned folder in the PyOBO cache.

.. code-block:: python

    import pyobo
    from scispacy.linking import EntityLinker

    linker = pyobo.get_scispacy_entity_linker("hgnc", filter_for_definitions=False)

Full Workflow
=============

Once an entity linker has been constructed, it can b used in series with a
:mod:`spacy.Language` object instantiated with :func:`spacy.load` to ground named
entities that were recognized by a model like ``en_core_web_sm``

.. code-block:: python

    import pyobo
    import spacy
    from scispacy.linking import EntityLinker
    from tabulate import tabulate

    linker: EntityLinker = pyobo.get_scispacy_entity_linker("hgnc", filter_for_definitions=False)

    # now, put it all together with a NER model
    nlp = spacy.load("en_core_web_sm")

    text = (
        "RAC(Rho family)-alpha serine/threonine-protein kinase "
        "is an enzyme that in humans is encoded by the AKT1 gene."
    )
    doc = linker(nlp(text))

    rows = [
        (
            span,
            span.start_char,
            span.end_char,
            f"`{curie} <https://bioregistry.io/{curie}>`_",
            score,
        )
        for span in doc.ents
        for curie, score in span._.kb_ents
    ]
    print(tabulate(rows, headers=["text", "start", "end", "prefix", "identifier"], tablefmt="rst"))

==== ===== === ============================================= ========
text start end curie                                         score
==== ===== === ============================================= ========
AKT1 100   104 `hgnc:391 <https://bioregistry.io/hgnc:391>`_ 1
AKT1 100   104 `hgnc:392 <https://bioregistry.io/hgnc:392>`_ 0.776504
AKT1 100   104 `hgnc:393 <https://bioregistry.io/hgnc:393>`_ 0.764049
==== ===== === ============================================= ========

This example recognizes the AKT serine/threonine kinase 1 (AKT1) gene and provides three
highly scored groundings, the best of which, `hgnc:391
<https://bioregistry.io/hgnc:391>`_, is correct.

.. note::

    The groundings and scores are stored by SciSpacy in the hidden attribute
    ``span._.kb_ents``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from typing_extensions import Unpack

from ..api.utils import get_version_from_kwargs
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
    *,
    ontology_kwargs: GetOntologyKwargs | None = None,
    candidate_generator_kwargs: dict[str, Any] | None = None,
    **entity_linker_kwargs: Any,
) -> EntityLinker:
    """Get a knowledgebase object for usage with :mod:`scispacy`.

    :param prefix :
        The ontology's prefix, such as ``go` for Gene Ontology, ``doid`` for the Disease
        Ontology, or more.

    :param ontology_kwargs: keyword arguments to pass to :func:`pyobo.get_ontology`,
        such as ``version``.
    :param candidate_generator_kwargs: keyword arguments to pass to
        :class:`scispacy.candidate_generation.CandidateGenerator`, such as ``ef_search``
    :param entity_linker_kwargs: keyword arguments to pass to
        :class:`scispacy.linking.EntityLinker`, such as ``ef_search``

    :returns: An object that can be applied in a :mod:`spacy` natural language
        processing workflow, namely to apply grounding/named entity normalization to
        recognized named entities.
    """
    from scispacy.linking import EntityLinker

    if ontology_kwargs is None:
        ontology_kwargs = {}

    version = get_version_from_kwargs(prefix, ontology_kwargs)
    scispacy_cache_directory = prefix_directory_join(prefix, "scispacy", version=version)

    # TODO see if we can skip loading the KB
    kb = get_scispacy_knowledgebase(prefix, **ontology_kwargs)
    linker = EntityLinker.from_kb(
        kb,
        ann_index_out_dir=scispacy_cache_directory.as_posix(),
        candidate_generator_kwargs=candidate_generator_kwargs,
        **(entity_linker_kwargs or {}),
    )
    return linker


def get_scispacy_knowledgebase(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> KnowledgeBase:
    """Get a knowledgebase object for usage with :mod:`scispacy`.

    :param prefix :
        The ontology's prefix, such as ``go` for Gene Ontology, ``doid`` for the Disease
        Ontology, or more.

    :param kwargs :
        keyword arguments to pass to :func:`pyobo.get_ontology`, such as ``version``.

    :returns: An object that represents a lexical index over name, synonym, and
        definition strings from the ontology.
    """
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

    # TODO reuse labels, synonyms, and definitions cache
    ontology = get_ontology(prefix, **kwargs)
    for term in ontology:
        yield Entity(
            concept_id=term.curie,
            canonical_name=term.name,
            aliases=[s.name for s in term.synonyms],
            definition=term.definition,
        )
