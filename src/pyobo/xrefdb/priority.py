"""Configuration for the default priority list."""

import bioregistry

__all__ = [
    "DEFAULT_PRIORITY_LIST",
]

_DEFAULT_PRIORITY_LIST = [
    # Genes
    "ncbigene",
    "hgnc",
    "rgd",
    "mgi",
    "ensembl",
    "uniprot",
    # Chemicals
    # 'inchikey',
    # 'inchi',
    # 'smiles',
    "pubchem.compound",
    "chebi",
    "drugbank",
    "chembl.compound",
    "zinc",
    # protein families and complexes (and famplexes :))
    "complexportal",
    "fplx",
    "ec-code",
    "interpro",
    "pfam",
    "signor",
    # Pathologies/phenotypes
    "mondo",
    "efo",
    "doid",
    "hp",
    # Taxa
    "ncbitaxon",
    # If you can get away from MeSH, do it
    "mesh",
    "icd",
]


def _get_default_priority_list():
    rv = []
    for _entry in _DEFAULT_PRIORITY_LIST:
        _prefix = bioregistry.normalize_prefix(_entry)
        if not _prefix:
            raise RuntimeError(f"unresolved prefix: {_entry}")
        if _prefix in rv:
            raise RuntimeError(f"duplicate found in priority list: {_entry}/{_prefix}")
        rv.append(_prefix)
    return rv


DEFAULT_PRIORITY_LIST = _get_default_priority_list()
del _get_default_priority_list
