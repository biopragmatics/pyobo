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
