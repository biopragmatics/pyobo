Named Entity Recognition
========================

PyOBO has high-level wrappers to construct literal mapping objects defined by
:mod:`ssslm.LiteralMapping`, which can be used to construct generic named entity
recognition (NER) and named entity normalization (NEN) tooling (e.g., using ScispaCy or
Gilda as a backend)

You can use :func:`pyobo.ground` as an integrated workflow:

.. code-block:: python

    import pyobo
    import ssslm

    matches: list[ssslm.Match] = pyobo.ground("chebi", "ethanol")

You can get the grounder directly first using :func:`pyobo.get_grounder`:

.. code-block:: python

    import pyobo
    import ssslm

    grounder: ssslm.Grounder = pyobo.get_grounder("chebi")
    matches: list[ssslm.Match] = grounder.get_matches("ethanol")

You can get the ontology directly using :func:`pyobo.get_ontology` then construct a
grounder with :meth:`pyobo.Obo.get_grounder`:

.. code-block:: python

    import pyobo
    import ssslm

    ontology: pyobo.Obo = pyobo.get_ontology("chebi")
    grounder: ssslm.Grounder = ontology.get_grounder()
    matches: list[ssslm.Match] = grounder.get_matches("ethanol")

You can load a custom ontology with :func:`pyobo.from_obo_path` then construct a
grounder with :meth:`pyobo.Obo.get_grounder`:

.. code-block:: python

    import pyobo
    import ssslm
    from urllib.request import urlretrieve

    url = "http://purl.obolibrary.org/obo/chebi.obo"
    path = "chebi.obo"
    urlretrieve(url, path)

    ontology: pyobo.Obo = pyobo.from_obo_path(path, prefix="chebi")
    grounder: ssslm.Grounder = ontology.get_grounder()
    matches: list[ssslm.Match] = grounder.get_matches("ethanol")

.. warning::

    When loading a custom ontology, it's required that the prefix is registered in the
    :mod:`bioregistry`, since PyOBO does additional standardization and normalization of
    prefixes, CURIEs, and URIs that are not part of the OBO specification.
