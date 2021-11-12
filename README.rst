PyOBO
=====
|build| |pypi_version| |python_versions| |pypi_license| |zenodo| |black| |bioregistry|

Tools for biological identifiers, names, synonyms, xrefs, hierarchies, relations, and properties through the
perspective of OBO.

Example Usage
-------------
Note! PyOBO is no-nonsense. This means that there's no repetitive
prefixes in identifiers. It also means all identifiers are strings,
no exceptions.

Note! The first time you run these, they have to download and cache
all resources. We're not in the business of redistributing data,
so all scripts should be completely reproducible. There's some
AWS tools for hosting/downloading pre-compiled versions in
``pyobo.aws`` if you don't have time for that.

Note! PyOBO can perform grounding in a limited number of cases, but
it is *not* a general solution for named entity recognition (NER) or grounding.
It's suggested to check `Gilda <https://github.com/indralab/gilda>`_
for a no-nonsense solution.

Mapping Identifiers and CURIEs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get mapping of ChEBI identifiers to names:

.. code-block:: python

   import pyobo

   chebi_id_to_name = pyobo.get_id_name_mapping('chebi')

   name = chebi_id_to_name['132964']
   assert name == 'fluazifop-P-butyl'

Or, you don't have time for two lines:

.. code-block:: python

    import pyobo

    name = pyobo.get_name('chebi', '132964')
    assert name == 'fluazifop-P-butyl'

Get reverse mapping of ChEBI names to identifiers:

.. code-block:: python

    import pyobo

    chebi_name_to_id = pyobo.get_name_id_mapping('chebi')

    identifier = chebi_name_to_id['fluazifop-P-butyl']
    assert identifier == '132964'

Maybe you live in CURIE world and just want to normalize something like
`CHEBI:132964`:

.. code-block:: python

    import pyobo

    name = pyobo.get_name_by_curie('CHEBI:132964')
    assert name == 'fluazifop-P-butyl'

Sometimes you accidentally got an old CURIE. It can be mapped to the more recent
one using alternative identifiers listed in the underlying OBO with:

.. code-block:: python

    import pyobo

    # Look up DNA-binding transcription factor activity (go:0003700)
    # based on an old id
    primary_curie = pyobo.get_primary_curie('go:0001071')
    assert primary_curie == 'go:0003700'

    # If it's already the primary, it just gets returned
    assert 'go:0003700' == pyobo.get_priority_curie('go:0003700')

Mapping Species
~~~~~~~~~~~~~~~
Some resources have species information for their term. Get a mapping of WikiPathway identifiers
to species (as NCBI taxonomy identifiers):

.. code-block:: python

    import pyobo

    wikipathways_id_to_species = pyobo.get_id_species_mapping('wikipathways')

    # Apoptosis (Homo sapiens)
    taxonomy_id = wikipathways_id_to_species['WP254']
    assert taxonomy_id == '9606'

Or, you don't have time for two lines:

.. code-block:: python

    import pyobo

    # Apoptosis (Homo sapiens)
    taxonomy_id = pyobo.get_species('wikipathways', 'WP254')
    assert taxonomy_id == '9606'

Grounding
~~~~~~~~~
Maybe you've got names/synonyms you want to try and map back to ChEBI synonyms.
Given the brand name `Fusilade II` of `CHEBI:132964`, it should be able to look
it up and its preferred label.

.. code-block:: python

    import pyobo

    prefix, identifier, name = pyobo.ground('chebi', 'Fusilade II')
    assert prefix == 'chebi'
    assert identifier == '132964'
    assert name == 'fluazifop-P-butyl'

    # When failure happens...
    prefix, identifier, name = pyobo.ground('chebi', 'Definitely not a real name')
    assert prefix is None
    assert identifier is None
    assert name is None

If you're not really sure which namespace a name might belong to, you
can try a few in a row (prioritize by ones that cover the appropriate
entity type to avoid false positives in case of conflicts):

.. code-block:: python

    import pyobo

    # looking for phenotypes/pathways
    prefix, identifier, name = pyobo.ground(['efo', 'go'], 'ERAD')
    assert prefix == 'go'
    assert identifier == '0030433'
    assert name == 'ubiquitin-dependent ERAD pathway'

Cross-referencing
~~~~~~~~~~~~~~~~~
Get xrefs from ChEBI to PubChem:

.. code-block:: python

    import pyobo

    chebi_id_to_pubchem_compound_id = pyobo.get_filtered_xrefs('chebi', 'pubchem.compound')

    pubchem_compound_id = chebi_id_to_pubchem_compound_id['132964']
    assert pubchem_compound_id == '3033674'

If you don't have time for two lines:

.. code-block:: python

    import pyobo

    pubchem_compound_id = pyobo.get_xref('chebi', '132964', 'pubchem.compound')
    assert pubchem_compound_id == '3033674'

Get xrefs from Entrez to HGNC, but they're only available through HGNC
so you need to flip them:

.. code-block:: python

    import pyobo

    hgnc_id_to_ncbigene_id = pyobo.get_filtered_xrefs('hgnc', 'ncbigene')
    ncbigene_id_to_hgnc_id = {
        ncbigene_id: hgnc_id
        for hgnc_id, ncbigene_id in hgnc_id_to_ncbigene_id.items()
    }
    mapt_hgnc = ncbigene_id_to_hgnc_id['4137']
    assert mapt_hgnc == '6893'

Since this is a common pattern, there's a keyword argument `flip`
that does this for you:

.. code-block:: python

    import pyobo

    ncbigene_id_to_hgnc_id = pyobo.get_filtered_xrefs('hgnc', 'ncbigene', flip=True)
    mapt_hgnc_id = ncbigene_id_to_hgnc_id['4137']
    assert mapt_hgnc_id == '6893'

If you don't have time for two lines (I admit this one is a bit confusing) and
need to flip it:

.. code-block:: python

    import pyobo

    hgnc_id = pyobo.get_xref('hgnc', '4137', 'ncbigene', flip=True)
    assert hgnc_id == '6893'

Remap a CURIE based on pre-defined priority list and `Inspector Javert's Xref
Database <https://cthoyt.com/2020/04/19/inspector-javerts-xref-database.html>`_:

.. code-block:: python

    import pyobo

    # Map to the best source possible
    mapt_ncbigene = pyobo.get_priority_curie('hgnc:6893')
    assert mapt_ncbigene == 'ncbigene:4137'

    # Sometimes you know you're the best. Own it.
    assert 'ncbigene:4137' == pyobo.get_priority_curie('ncbigene:4137')

Find all CURIEs mapped to a given one using Inspector Javert's Xref Database:

.. code-block:: python

    import pyobo

    # Get a set of all CURIEs mapped to MAPT
    mapt_curies = pyobo.get_equivalent('hgnc:6893')
    assert 'ncbigene:4137' in mapt_curies
    assert 'ensembl:ENSG00000186868' in mapt_curies

If you don't want to wait to build the database locally for the ``pyobo.get_priority_curie`` and
``pyobo.get_equivalent``, you can use the following code to download a release from
`Zenodo <https://zenodo.org/record/3757266>`_:

.. code-block:: python

    import pyobo.resource_utils

    pyobo.resource_utils.ensure_inspector_javert()

Properties
~~~~~~~~~~
Get properties, like SMILES. The semantics of these are defined on an OBO-OBO basis.

.. code-block:: python

    import pyobo

    # I don't make the rules. I wouldn't have chosen this as the key for this property. It could be any string
    chebi_smiles_property = 'http://purl.obolibrary.org/obo/chebi/smiles'
    chebi_id_to_smiles = pyobo.get_filtered_properties_mapping('chebi', chebi_smiles_property)

    smiles = chebi_id_to_smiles['132964']
    assert smiles == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'

If you don't have time for two lines:

.. code-block:: python

    import pyobo

    smiles = pyobo.get_property('chebi', '132964', 'http://purl.obolibrary.org/obo/chebi/smiles')
    assert smiles == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'

Hierarchy
~~~~~~~~~
Check if an entity is in the hierarchy:

.. code-block:: python

    import networkx as nx
    import pyobo

    # check that go:0008219 ! cell death is an ancestor of go:0006915 ! apoptotic process
    assert 'go:0008219' in pyobo.get_ancestors('go', '0006915')

    # check that go:0070246 ! natural killer cell apoptotic process is a
    # descendant of go:0006915 ! apoptotic process
    apopototic_process_descendants = pyobo.get_descendants('go', '0006915')
    assert 'go:0070246' in apopototic_process_descendants

Get the subhierarchy below a given node:

.. code-block:: python

    # get the descendant graph of go:0006915 ! apoptotic process
    apopototic_process_subhierarchy = pyobo.get_subhierarchy('go', '0006915')

    # check that go:0070246 ! natural killer cell apoptotic process is a
    # descendant of go:0006915 ! apoptotic process through the subhierarchy
    assert 'go:0070246' in apopototic_process_subhierarchy

Get a hierarchy with properties pre-loaded in the node data dictionaries:

.. code-block:: python

    import pyobo

    prop = 'http://purl.obolibrary.org/obo/chebi/smiles'
    chebi_hierarchy = pyobo.get_hierarchy('chebi', properties=[prop])

    assert 'chebi:132964' in chebi_hierarchy
    assert prop in chebi_hierarchy.nodes['chebi:132964']
    assert chebi_hierarchy.nodes['chebi:132964'][prop] == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'

Relations
~~~~~~~~~
Get all orthologies (``ro:HOM0000017``) between HGNC and MGI (note: this is one way)

.. code-block:: python

    >>> import pyobo
    >>> human_mapt_hgnc_id = '6893'
    >>> mouse_mapt_mgi_id = '97180'
    >>> hgnc_mgi_orthology_mapping = pyobo.get_relation_mapping('hgnc', 'ro:HOM0000017', 'mgi')
    >>> assert mouse_mapt_mgi_id == hgnc_mgi_orthology_mapping[human_mapt_hgnc_id]

If you want to do it in one line, use:

.. code-block:: python

    >>> import pyobo
    >>> human_mapt_hgnc_id = '6893'
    >>> mouse_mapt_mgi_id = '97180'
    >>> assert mouse_mapt_mgi_id == pyobo.get_relation('hgnc', 'ro:HOM0000017', 'mgi', human_mapt_hgnc_id)

Writings Tests that Use PyOBO
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you're writing your own code that relies on PyOBO, and unit
testing it (as you should) in a continuous integration setting,
you've probably realized that loading all of the resources on each
build is not so fast. In those scenarios, you can use some of the
pre-build patches like in the following:

.. code-block:: python

    import unittest
    import pyobo
    from pyobo.mocks import get_mock_id_name_mapping

    mock_id_name_mapping = get_mock_id_name_mapping({
        'chebi': {
            '132964': 'fluazifop-P-butyl',
        },
    })

    class MyTestCase(unittest.TestCase):
        def my_test(self):
            with mock_id_name_mapping:
                # use functions directly, or use your functions that wrap them
                pyobo.get_name('chebi', '1234')


Installation
------------
PyOBO can be installed from `PyPI <https://pypi.org/project/pyobo/>`_ with:

.. code-block:: sh

    $ pip install pyobo

It can be installed in development mode from `GitHub <https://github.com/pyobo/pyobo>`_
with:

.. code-block:: sh

    $ git clone https://github.com/pyobo/pyobo.git
    $ cd pyobo
    $ pip install -e .

Curation of the Bioregistry
---------------------------
In order to normalize references and identify resources, PyOBO uses the
`Bioregistry <https://github.com/bioregistry/bioregistry>`_. It used to be a part of PyOBO, but has since
been externalized for more general reuse.

At `src/pyobo/registries/metaregistry.json <https://github.com/pyobo/pyobo/blob/master/src/pyobo/registries/metaregistry.json>`_
is the curated "metaregistry". This is a source of information that contains
all sorts of fixes for missing/wrong information in MIRIAM, OLS, and OBO Foundry; entries that don't appear in
any of them; additional synonym information for each namespace/prefix; rules for normalizing xrefs and CURIEs, etc.

Other entries in the metaregistry:

- The ``"remappings"->"full"`` entry is a dictionary from strings that might follow ``xref:``
  in a given OBO file that need to be completely replaced, due to incorrect formatting
- The ``"remappings"->"prefix"`` entry contains a dictionary of prefixes for xrefs that need
  to be remapped. Several rules, for example, remove superfluous spaces that occur inside
  CURIEs or and others address instances of the GOGO issue.
- The ``"blacklists"`` entry contains rules for throwing out malformed xrefs based on
  full string, just prefix, or just suffix.

Troubleshooting
---------------
The OBO Foundry seems to be pretty unstable with respect to the URLs to OBO resources. If you get an error like:

.. code-block::

   pyobo.getters.MissingOboBuild: OBO Foundry is missing a build for: mondo

Then you should check the corresponding page on the OBO Foundry (in this case, http://www.obofoundry.org/ontology/mondo.html)
and make update to the ``url`` entry for that namespace in the Bioregistry.

.. |build| image:: https://github.com/pyobo/pyobo/workflows/Tests/badge.svg
    :target: https://github.com/pyobo/pyobo/actions?query=workflow%3ATests
    :alt: Build Status

.. |coverage| image:: https://codecov.io/gh/pyobo/pyobo/coverage.svg?branch=master
    :target: https://codecov.io/gh/pyobo/pyobo?branch=master
    :alt: Coverage Status

.. |docs| image:: http://readthedocs.org/projects/pyobo/badge/?version=latest
    :target: http://pyobo.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. |python_versions| image:: https://img.shields.io/pypi/pyversions/pyobo.svg
    :alt: Stable Supported Python Versions

.. |pypi_version| image:: https://img.shields.io/pypi/v/pyobo.svg
    :alt: Current version on PyPI

.. |pypi_license| image:: https://img.shields.io/pypi/l/pyobo.svg
    :alt: MIT License

.. |zenodo| image:: https://zenodo.org/badge/203449095.svg
    :target: https://zenodo.org/badge/latestdoi/203449095
    :alt: Zenodo

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Black Code Style

.. |bioregistry| image:: https://img.shields.io/static/v1?label=Powered%20by&message=Bioregistry&color=BA274A&style=flat&logo=image/png;base64,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
    :target: https://github.com/biopragmatics/bioregistry
    :alt: Powered by the Bioregistry
