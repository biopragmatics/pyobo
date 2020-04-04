# -*- coding: utf-8 -*-

"""Constants for PyOBO."""

import os

__all__ = [
    'PYOBO_HOME',
    'OUTPUT_DIRECTORY',
    'CURATED_URLS',
    'SPECIES_REMAPPING',
]

PYOBO_HOME = os.environ.get('PYOBO_HOME') or os.path.join(os.path.expanduser('~'), '.obo')

OUTPUT_DIRECTORY = (
    os.environ.get('PYOBO_OUTPUT')
    or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'obo'))
)

#: A curated list of prefixes to URLs for OBO files that aren't properly listed in OBO Foundry
CURATED_URLS = {
    'mp': 'http://purl.obolibrary.org/obo/mp.obo',
    'chiro': 'http://purl.obolibrary.org/obo/chiro.obo',
    'ncbitaxon': 'http://purl.obolibrary.org/obo/ncbitaxon.obo',
    'mpath': 'https://raw.githubusercontent.com/PaulNSchofield/mpath/master/mpath.obo',
    'uberon': 'http://purl.obolibrary.org/obo/uberon/basic.obo',
    'idomal': 'http://purl.obolibrary.org/obo/idomal.obo',
    'aeo': 'https://raw.githubusercontent.com/obophenotype/human-developmental-anatomy-ontology/'
           'master/src/ontology/aeo.obo',
    'bspo': 'https://raw.githubusercontent.com/obophenotype/biological-spatial-ontology/master/bspo.obo',
    'ceph': 'https://raw.githubusercontent.com/obophenotype/cephalopod-ontology/master/ceph.obo',
    'cl': 'https://raw.githubusercontent.com/obophenotype/cell-ontology/master/cl-full.obo',
    'cro': 'https://raw.githubusercontent.com/data2health/contributor-role-ontology/master/cro.obo',
    'cteno': 'https://raw.githubusercontent.com/obophenotype/ctenophore-ontology/master/cteno.obo',
    'ddpheno': 'https://raw.githubusercontent.com/obophenotype/dicty-phenotype-ontology/master/ddpheno.obo',
    'geno': 'https://raw.githubusercontent.com/monarch-initiative/GENO-ontology/develop/geno-full.obo',
    'hp': 'http://purl.obolibrary.org/obo/hp.obo',
    'miro': 'http://purl.obolibrary.org/obo/miro.obo',
    'tads': 'http://purl.obolibrary.org/obo/tads.obo',
    'tgma': 'http://purl.obolibrary.org/obo/tgma.obo',
}

SPECIES_REMAPPING = {
    'Canis familiaris': 'Canis lupus familiaris',
}
