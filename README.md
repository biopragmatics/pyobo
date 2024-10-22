<!--
<p align="center">
  <img src="https://github.com/biopragmatics/pyobo/raw/main/docs/source/logo.png" height="150">
</p>
-->

<h1 align="center">
  PyOBO
</h1>

<p align="center">
    <a href="https://github.com/biopragmatics/pyobo/actions/workflows/tests.yml">
        <img alt="Tests" src="https://github.com/biopragmatics/pyobo/actions/workflows/tests.yml/badge.svg" /></a>
    <a href="https://pypi.org/project/pyobo">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/pyobo" /></a>
    <a href="https://pypi.org/project/pyobo">
        <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/pyobo" /></a>
    <a href="https://github.com/biopragmatics/pyobo/blob/main/LICENSE">
        <img alt="PyPI - License" src="https://img.shields.io/pypi/l/pyobo" /></a>
    <a href='https://pyobo.readthedocs.io/en/latest/?badge=latest'>
        <img src='https://readthedocs.org/projects/pyobo/badge/?version=latest' alt='Documentation Status' /></a>
    <a href="https://codecov.io/gh/biopragmatics/pyobo/branch/main">
        <img src="https://codecov.io/gh/biopragmatics/pyobo/branch/main/graph/badge.svg" alt="Codecov status" /></a>  
    <a href="https://github.com/cthoyt/cookiecutter-python-package">
        <img alt="Cookiecutter template from @cthoyt" src="https://img.shields.io/badge/Cookiecutter-snekpack-blue" /></a>
    <a href='https://github.com/psf/black'>
        <img src='https://img.shields.io/badge/code%20style-black-000000.svg' alt='Code style: black' /></a>
    <a href="https://github.com/biopragmatics/pyobo/blob/main/.github/CODE_OF_CONDUCT.md">
        <img src="https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg" alt="Contributor Covenant"/></a>
</p>

Tools for biological identifiers, names, synonyms, xrefs, hierarchies, relations, and properties through the
perspective of OBO.

## Example Usage

Note! PyOBO is no-nonsense. This means that there's no repetitive
prefixes in identifiers. It also means all identifiers are strings,
no exceptions.

Note! The first time you run these, they have to download and cache
all resources. We're not in the business of redistributing data,
so all scripts should be completely reproducible. There's some
AWS tools for hosting/downloading pre-compiled versions in
`pyobo.aws` if you don't have time for that.

Note! PyOBO can perform grounding in a limited number of cases, but
it is *not* a general solution for named entity recognition (NER) or grounding.
It's suggested to check `Gilda <https://github.com/indralab/gilda>`_
for a no-nonsense solution.

### Mapping Identifiers and CURIEs

Get mapping of ChEBI identifiers to names:

```python
import pyobo

chebi_id_to_name = pyobo.get_id_name_mapping('chebi')

name = chebi_id_to_name['132964']
assert name == 'fluazifop-P-butyl'
```

Or, you don't have time for two lines:

```python
import pyobo

name = pyobo.get_name('chebi', '132964')
assert name == 'fluazifop-P-butyl'
```

Get reverse mapping of ChEBI names to identifiers:

```python
import pyobo

chebi_name_to_id = pyobo.get_name_id_mapping('chebi')

identifier = chebi_name_to_id['fluazifop-P-butyl']
assert identifier == '132964'
```

Maybe you live in CURIE world and just want to normalize something like
`CHEBI:132964`:

```python
import pyobo

name = pyobo.get_name_by_curie('CHEBI:132964')
assert name == 'fluazifop-P-butyl'
```

Sometimes you accidentally got an old CURIE. It can be mapped to the more recent
one using alternative identifiers listed in the underlying OBO with:

```python
import pyobo

# Look up DNA-binding transcription factor activity (go:0003700)
# based on an old id
primary_curie = pyobo.get_primary_curie('go:0001071')
assert primary_curie == 'go:0003700'

# If it's already the primary, it just gets returned
assert 'go:0003700' == pyobo.get_priority_curie('go:0003700')
```

### Mapping Species

Some resources have species information for their term. Get a mapping of WikiPathway identifiers
to species (as NCBI taxonomy identifiers):

```python
import pyobo

wikipathways_id_to_species = pyobo.get_id_species_mapping('wikipathways')

# Apoptosis (Homo sapiens)
taxonomy_id = wikipathways_id_to_species['WP254']
assert taxonomy_id == '9606'
```

Or, you don't have time for two lines:

```python
import pyobo

# Apoptosis (Homo sapiens)
taxonomy_id = pyobo.get_species('wikipathways', 'WP254')
assert taxonomy_id == '9606'
```

### Grounding

Maybe you've got names/synonyms you want to try and map back to ChEBI synonyms.
Given the brand name `Fusilade II` of `CHEBI:132964`, it should be able to look
it up and its preferred label.

```python
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
```

If you're not really sure which namespace a name might belong to, you
can try a few in a row (prioritize by ones that cover the appropriate
entity type to avoid false positives in case of conflicts):

```python
import pyobo

# looking for phenotypes/pathways
prefix, identifier, name = pyobo.ground(['efo', 'go'], 'ERAD')
assert prefix == 'go'
assert identifier == '0030433'
assert name == 'ubiquitin-dependent ERAD pathway'
```

### Cross-referencing

Get xrefs from ChEBI to PubChem:

```python
import pyobo

chebi_id_to_pubchem_compound_id = pyobo.get_filtered_xrefs('chebi', 'pubchem.compound')

pubchem_compound_id = chebi_id_to_pubchem_compound_id['132964']
assert pubchem_compound_id == '3033674'
```

If you don't have time for two lines:

```python
import pyobo

pubchem_compound_id = pyobo.get_xref('chebi', '132964', 'pubchem.compound')
assert pubchem_compound_id == '3033674'
```

Get xrefs from Entrez to HGNC, but they're only available through HGNC,
so you need to flip them:

```python
import pyobo

hgnc_id_to_ncbigene_id = pyobo.get_filtered_xrefs('hgnc', 'ncbigene')
ncbigene_id_to_hgnc_id = {
  ncbigene_id: hgnc_id
  for hgnc_id, ncbigene_id in hgnc_id_to_ncbigene_id.items()
}
mapt_hgnc = ncbigene_id_to_hgnc_id['4137']
assert mapt_hgnc == '6893'
```

Since this is a common pattern, there's a keyword argument `flip`
that does this for you:

```python
import pyobo

ncbigene_id_to_hgnc_id = pyobo.get_filtered_xrefs('hgnc', 'ncbigene', flip=True)
mapt_hgnc_id = ncbigene_id_to_hgnc_id['4137']
assert mapt_hgnc_id == '6893'
```

If you don't have time for two lines (I admit this one is a bit confusing) and
need to flip it:

```python
import pyobo

hgnc_id = pyobo.get_xref('hgnc', '4137', 'ncbigene', flip=True)
assert hgnc_id == '6893'
```

Remap a CURIE based on pre-defined priority list and [Inspector Javert's Xref
Database](https://cthoyt.com/2020/04/19/inspector-javerts-xref-database.html):

```python

import pyobo

# Map to the best source possible
mapt_ncbigene = pyobo.get_priority_curie('hgnc:6893')
assert mapt_ncbigene == 'ncbigene:4137'

# Sometimes you know you're the best. Own it.
assert 'ncbigene:4137' == pyobo.get_priority_curie('ncbigene:4137')
```

Find all CURIEs mapped to a given one using Inspector Javert's Xref Database:

```python
import pyobo

# Get a set of all CURIEs mapped to MAPT
mapt_curies = pyobo.get_equivalent('hgnc:6893')
assert 'ncbigene:4137' in mapt_curies
assert 'ensembl:ENSG00000186868' in mapt_curies
```

If you don't want to wait to build the database locally for the `pyobo.get_priority_curie` and
`pyobo.get_equivalent`, you can use the following code to download a release from
[Zenodo](https://zenodo.org/record/3757266):

```python
import pyobo.resource_utils

pyobo.resource_utils.ensure_inspector_javert()
```

### Properties

Get properties, like SMILES. The semantics of these are defined on an OBO-OBO basis.

```python
import pyobo

# I don't make the rules. I wouldn't have chosen this as the key for this property. It could be any string
chebi_smiles_property = 'http://purl.obolibrary.org/obo/chebi/smiles'
chebi_id_to_smiles = pyobo.get_filtered_properties_mapping('chebi', chebi_smiles_property)

smiles = chebi_id_to_smiles['132964']
assert smiles == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'
```

If you don't have time for two lines:

```python
import pyobo

smiles = pyobo.get_property('chebi', '132964', 'http://purl.obolibrary.org/obo/chebi/smiles')
assert smiles == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'
```

### Hierarchy

Check if an entity is in the hierarchy:

```python
import networkx as nx
import pyobo

# check that go:0008219 ! cell death is an ancestor of go:0006915 ! apoptotic process
assert 'go:0008219' in pyobo.get_ancestors('go', '0006915')

# check that go:0070246 ! natural killer cell apoptotic process is a
# descendant of go:0006915 ! apoptotic process
apopototic_process_descendants = pyobo.get_descendants('go', '0006915')
assert 'go:0070246' in apopototic_process_descendants
```

Get the sub-hierarchy below a given node:

```python
import pyobo

# get the descendant graph of go:0006915 ! apoptotic process
apopototic_process_subhierarchy = pyobo.get_subhierarchy('go', '0006915')

# check that go:0070246 ! natural killer cell apoptotic process is a
# descendant of go:0006915 ! apoptotic process through the subhierarchy
assert 'go:0070246' in apopototic_process_subhierarchy
```

Get a hierarchy with properties preloaded in the node data dictionaries:

```python
import pyobo

prop = 'http://purl.obolibrary.org/obo/chebi/smiles'
chebi_hierarchy = pyobo.get_hierarchy('chebi', properties=[prop])

assert 'chebi:132964' in chebi_hierarchy
assert prop in chebi_hierarchy.nodes['chebi:132964']
assert chebi_hierarchy.nodes['chebi:132964'][prop] == 'C1(=CC=C(N=C1)OC2=CC=C(C=C2)O[C@@H](C(OCCCC)=O)C)C(F)(F)F'
```

### Relations

Get all orthologies (`ro:HOM0000017`) between HGNC and MGI (note: this is one way)

```python
>>> import pyobo
>>> human_mapt_hgnc_id = '6893'
>>> mouse_mapt_mgi_id = '97180'
>>> hgnc_mgi_orthology_mapping = pyobo.get_relation_mapping('hgnc', 'ro:HOM0000017', 'mgi')
>>> assert mouse_mapt_mgi_id == hgnc_mgi_orthology_mapping[human_mapt_hgnc_id]
```

If you want to do it in one line, use:

```python

>>> import pyobo
>>> human_mapt_hgnc_id = '6893'
>>> mouse_mapt_mgi_id = '97180'
>>> assert mouse_mapt_mgi_id == pyobo.get_relation('hgnc', 'ro:HOM0000017', 'mgi', human_mapt_hgnc_id)
```

### Writings Tests that Use PyOBO

If you're writing your own code that relies on PyOBO, and unit
testing it (as you should) in a continuous integration setting,
you've probably realized that loading all of the resources on each
build is not so fast. In those scenarios, you can use some of the
pre-build patches like in the following:

```python
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
```


## Curation of the Bioregistry

In order to normalize references and identify resources, PyOBO uses the
[Bioregistry](https://github.com/bioregistry/bioregistry). It used to be a part of PyOBO, but has since
been externalized for more general reuse.

At [src/pyobo/registries/metaregistry.json](https://github.com/pyobo/pyobo/blob/master/src/pyobo/registries/metaregistry.json)
is the curated "metaregistry". This is a source of information that contains
all sorts of fixes for missing/wrong information in MIRIAM, OLS, and OBO Foundry; entries that don't appear in
any of them; additional synonym information for each namespace/prefix; rules for normalizing xrefs and CURIEs, etc.

Other entries in the metaregistry:

- The `"remappings"->"full"` entry is a dictionary from strings that might follow `xref:`
  in a given OBO file that need to be completely replaced, due to incorrect formatting
- The `"remappings"->"prefix"` entry contains a dictionary of prefixes for xrefs that need
  to be remapped. Several rules, for example, remove superfluous spaces that occur inside
  CURIEs or and others address instances of the GOGO issue.
- The `"blacklists"` entry contains rules for throwing out malformed xrefs based on
  full string, just prefix, or just suffix.

## Troubleshooting

The OBO Foundry seems to be pretty unstable with respect to the URLs to OBO resources. If you get an error like:

```
pyobo.getters.MissingOboBuild: OBO Foundry is missing a build for: mondo
```

Then you should check the corresponding page on the OBO Foundry (in this case, http://www.obofoundry.org/ontology/mondo.html)
and make update to the `url` entry for that namespace in the Bioregistry.

## 🚀 Installation

The most recent release can be installed from
[PyPI](https://pypi.org/project/pyobo/) with:

```shell
pip install pyobo
```

The most recent code and data can be installed directly from GitHub with:

```shell
pip install git+https://github.com/biopragmatics/pyobo.git
```

## 👐 Contributing

Contributions, whether filing an issue, making a pull request, or forking, are appreciated. See
[CONTRIBUTING.md](https://github.com/biopragmatics/pyobo/blob/master/.github/CONTRIBUTING.md)
for more information on getting involved.

## 👋 Attribution

### ⚖️ License

The code in this package is licensed under the MIT License.

<!--
### 📖 Citation

Citation goes here!
-->

<!--
### 🎁 Support

This project has been supported by the following organizations (in alphabetical order):

- [Biopragmatics Lab](https://biopragmatics.github.io)

-->

<!--
### 💰 Funding

This project has been supported by the following grants:

| Funding Body  | Program                                                      | Grant Number |
|---------------|--------------------------------------------------------------|--------------|
| Funder        | [Grant Name (GRANT-ACRONYM)](https://example.com/grant-link) | ABCXYZ       |
-->

### 🍪 Cookiecutter

This package was created with [@audreyfeldroy](https://github.com/audreyfeldroy)'s
[cookiecutter](https://github.com/cookiecutter/cookiecutter) package using [@cthoyt](https://github.com/cthoyt)'s
[cookiecutter-snekpack](https://github.com/cthoyt/cookiecutter-snekpack) template.

## 🛠️ For Developers

<details>
  <summary>See developer instructions</summary>

The final section of the README is for if you want to get involved by making a code contribution.

### Development Installation

To install in development mode, use the following:

```bash
git clone git+https://github.com/biopragmatics/pyobo.git
cd pyobo
pip install -e .
```

### Updating Package Boilerplate

This project uses `cruft` to keep boilerplate (i.e., configuration, contribution guidelines, documentation
configuration)
up-to-date with the upstream cookiecutter package. Update with the following:

```shell
pip install cruft
cruft update
```

More info on Cruft's update command is
available [here](https://github.com/cruft/cruft?tab=readme-ov-file#updating-a-project).

### 🥼 Testing

After cloning the repository and installing `tox` with `pip install tox tox-uv`, 
the unit tests in the `tests/` folder can be run reproducibly with:

```shell
tox -e py
```

Additionally, these tests are automatically re-run with each commit in a
[GitHub Action](https://github.com/biopragmatics/pyobo/actions?query=workflow%3ATests).

### 📖 Building the Documentation

The documentation can be built locally using the following:

```shell
git clone git+https://github.com/biopragmatics/pyobo.git
cd pyobo
tox -e docs
open docs/build/html/index.html
``` 

The documentation automatically installs the package as well as the `docs`
extra specified in the [`pyproject.toml`](../../Desktop/pyobo/pyproject.toml). `sphinx` plugins
like `texext` can be added there. Additionally, they need to be added to the
`extensions` list in [`docs/source/conf.py`](../../Desktop/pyobo/docs/source/conf.py).

The documentation can be deployed to [ReadTheDocs](https://readthedocs.io) using
[this guide](https://docs.readthedocs.io/en/stable/intro/import-guide.html).
The [`.readthedocs.yml`](../../Desktop/pyobo/.readthedocs.yml) YAML file contains all the configuration you'll need.
You can also set up continuous integration on GitHub to check not only that
Sphinx can build the documentation in an isolated environment (i.e., with `tox -e docs-test`)
but also that [ReadTheDocs can build it too](https://docs.readthedocs.io/en/stable/pull-requests.html).

#### Configuring ReadTheDocs

1. Log in to ReadTheDocs with your GitHub account to install the integration
   at https://readthedocs.org/accounts/login/?next=/dashboard/
2. Import your project by navigating to https://readthedocs.org/dashboard/import then clicking the plus icon next to
   your repository
3. You can rename the repository on the next screen using a more stylized name (i.e., with spaces and capital letters)
4. Click next, and you're good to go!

### 📦 Making a Release

#### Configuring Zenodo

[Zenodo](https://zenodo.org) is a long-term archival system that assigns a DOI to each release of your package.

1. Log in to Zenodo via GitHub with this link: https://zenodo.org/oauth/login/github/?next=%2F. This brings you to a
   page that lists all of your organizations and asks you to approve installing the Zenodo app on GitHub. Click "grant"
   next to any organizations you want to enable the integration for, then click the big green "approve" button. This
   step only needs to be done once.
2. Navigate to https://zenodo.org/account/settings/github/, which lists all of your GitHub repositories (both in your
   username and any organizations you enabled). Click the on/off toggle for any relevant repositories. When you make
   a new repository, you'll have to come back to this

After these steps, you're ready to go! After you make "release" on GitHub (steps for this are below), you can navigate
to https://zenodo.org/account/settings/github/repository/biopragmatics/pyobo
to see the DOI for the release and link to the Zenodo record for it.

#### Registering with the Python Package Index (PyPI)

You only have to do the following steps once.

1. Register for an account on the [Python Package Index (PyPI)](https://pypi.org/account/register)
2. Navigate to https://pypi.org/manage/account and make sure you have verified your email address. A verification email
   might not have been sent by default, so you might have to click the "options" dropdown next to your address to get to
   the "re-send verification email" button
3. 2-Factor authentication is required for PyPI since the end of 2023 (see
   this [blog post from PyPI](https://blog.pypi.org/posts/2023-05-25-securing-pypi-with-2fa/)). This means
   you have to first issue account recovery codes, then set up 2-factor authentication
4. Issue an API token from https://pypi.org/manage/account/token

#### Configuring your machine's connection to PyPI

You have to do the following steps once per machine. Create a file in your home directory called
`.pypirc` and include the following:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = <the API token you just got>

# This block is optional in case you want to be able to make test releases to the Test PyPI server
[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = <an API token from test PyPI>
```

Note that since PyPI is requiring token-based authentication, we use `__token__` as the user, verbatim.
If you already have a `.pypirc` file with a `[distutils]` section, just make sure that there is an `index-servers`
key and that `pypi` is in its associated list. More information on configuring the `.pypirc` file can
be found [here](https://packaging.python.org/en/latest/specifications/pypirc).

#### Uploading to PyPI

After installing the package in development mode and installing
`tox` with `pip install tox tox-uv`,
run the following from the shell:

```shell
tox -e finish
```

This script does the following:

1. Uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to switch the version number in
   the `pyproject.toml`, `CITATION.cff`, `src/pyobo/version.py`,
   and [`docs/source/conf.py`](../../Desktop/pyobo/docs/source/conf.py) to not have the `-dev` suffix
2. Packages the code in both a tar archive and a wheel using
   [`uv build`](https://docs.astral.sh/uv/guides/publish/#building-your-package)
3. Uploads to PyPI using [`twine`](https://github.com/pypa/twine).
4. Push to GitHub. You'll need to make a release going with the commit where the version was bumped.
5. Bump the version to the next patch. If you made big changes and want to bump the version by minor, you can
   use `tox -e bumpversion -- minor` after.

#### Releasing on GitHub

1. Navigate
   to https://github.com/biopragmatics/pyobo/releases/new
   to draft a new release
2. Click the "Choose a Tag" dropdown and select the tag corresponding to the release you just made
3. Click the "Generate Release Notes" button to get a quick outline of recent changes. Modify the title and description
   as you see fit
4. Click the big green "Publish Release" button

This will trigger Zenodo to assign a DOI to your release as well.

</details>
