PyOBO |build|
=============
Tools for biological identifiers, names, synonyms, xrefs, hierarchies, relations, and properties through the
perspective of OBO.

Example Usage
-------------
Note! PyOBO is no nonsense. This means that there's no repetitive
prefixes in identifiers. It also means all identifiers are strings,
no exceptions.

Note! The first time you run these, they have to download and cache
all resources. We're not in the business of redistributing data,
so all scripts should be completely reproducible. There's some
AWS tools for hosting/downloading pre-compiled versions in
``pyobo.aws`` if you don't have time for that.

Get mapping of ChEBI identifiers to names.

.. code-block:: python

   import pyobo

   chebi_id_to_name = pyobo.get_id_name_mapping('chebi')

   name = chebi_id_to_name['132964']
   assert name == 'fluazifop-P-butyl'

Or, you don't have time for two lines

.. code-block:: python

    import pyobo

    name = pyobo.get_name('chebi', '132964')
    assert name == 'fluazifop-P-butyl'

Get reverse mapping of ChEBI names to identifiers

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


Get xrefs from ChEBI to PubChem

.. code-block:: python

    import pyobo

    chebi_id_to_pubchem_compound_id = pyobo.get_filtered_xrefs('chebi', 'pubchem.compound')

    pubchem_compound_id = chebi_id_to_pubchem_compound_id['132964']
    assert pubchem_compound_id == '3033674'

Get xrefs from Entrez to HGNC, but they're only available through HGNC
so you need to flip them

.. code-block:: python

    import pyobo

    hgnc_id_to_ncbigene_id = pyobo.get_filtered_xrefs('hgnc', 'ncbigene')
    ncbigene_id_to_hgnc_id = {
        ncbigene_id: hgnc_id 
        for hgnc_id, ncbigene_id in hgnc_id_to_ncbigene_id.items()
    }

Get properties, like SMILES. The semantics of these are defined on an OBO-OBO basis.

.. code-block:: python

    import pyobo

    # I dont make the rules. I wouldn't have chosen this as the key for this property. It could be any string
    chebi_smiles_property = 'http://purl.obolibrary.org/obo/chebi/smiles'
    chebi_id_to_smiles = pyobo.get_filtered_properties_mapping('chebi', chebi_smiles_property)

    smiles = chebi_id_to_smiles['132964']
    assert smiles == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'

Installation |pypi_version| |python_versions| |pypi_license|
------------------------------------------------------------
PyOBO can be installed from `PyPI <https://pypi.org/project/pyobo/>`_ with:

.. code-block:: sh

    $ pip install pyobo

It can be installed in development mode from `GitHub <https://github.com/pyobo/pyobo>`_
with:

.. code-block:: sh

    $ git clone https://github.com/pyobo/pyobo.git
    $ cd pyobo
    $ pip install -e .

Curation of the Metaregistry
----------------------------
At src/pyobo/registries/metaregistry.json is the curated registry. This is a source of information that contains
all sorts of fixes for missing/wrong information in MIRIAM, OLS, and OBO Foundry; entries that don't appear in
any of them; additional synonym information for each namespace/prefix; rules for normalizing xrefs and CURIEs, etc.

Most users will be interested in the ``"database"`` subdictionary.
Each entry has a key that was chosen first by preference for MIRIAM, then OBO Foundry,
then OLS, or assigned based on what felt right/was how they appeared in xrefs in other OBO files.
Their corresponding entries can have some combination of these keys:

- ``title``
- ``pattern``, a regex string for identifiers
- ``url``, a url pattern to resolve identifiers. Uses $1 to represent the identifier.
- ``synonyms``, a list of alternative prefixes that should point to this
- ``download``, a URL to the OBO file in case OBO Foundry doesn't list it or has a mistake
- ``not_available_as_obo``, a boolean telling you exactly what it sounds like
- ``no_own_terms``, a boolean telling you if it is completely derived from external sources
- ``wikidata_property``, a string pointing to the wikidata property that connects item in WikiData
  to identifers in this namespace
- ``miriam``: a dictionary containing "id" and "prefix" to point to MIRIAM
- ``obofoundry``: a dictionary containing "prefix" to point to OBO Foundry
- ``ols``, a dictionary containing "ontologyId" to point to OLS

Other entries in the metaregistry:

- The ``"remappings"->"full"`` entry is a dictionary from strings that might follow ``xref:``
  in a given OBO file that need to be completely replaced, due to incorrect formatting
- The ``"remappings"->"prefix"`` entry contains a dictionary of prefixes for xrefs that need
  to be remapped. Several rules, for example, remove superfluous spaces that occur inside
  CURIEs or and others address instances of the GOGO issue.
- The ``"obsolete"`` entry maps prefixes that have been changed.
- The ``"blacklists"`` entry contains rules for throwing out malformed xrefs based on
  full string, just prefix, or just suffix.

Development
-----------
Update the registries with the following commands. These external resources get updated all the
time, so don't forget about this.

.. code-block:: bash

    $ python -m pyobo.registries.obofoundry
    $ python -m pyobo.registries.ols
    $ python -m pyobo.registries.miriam


.. |build| image:: https://travis-ci.com/pyobo/pyobo.svg?branch=master
    :target: https://travis-ci.com/pyobo/pyobo
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
