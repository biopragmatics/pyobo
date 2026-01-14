"""Converter for PubChem Compound."""

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path

import pandas as pd
from bioregistry.utils import removeprefix
from tqdm.auto import tqdm

from ..api import get_name_id_mapping
from ..api.utils import get_version
from ..struct import Obo, Reference, Synonym, Term
from ..utils.iter import iterate_gzips_together
from ..utils.path import ensure_df, ensure_path

__all__ = [
    "PubChemCompoundGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "pubchem.compound"


def _get_pubchem_extras_url(version: str | None, end: str) -> str:
    if version is None:
        version = get_version("pubchem")
    return f"ftp://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Monthly/{version}/Extras/{end}"


class PubChemCompoundGetter(Obo):
    """An ontology representation of the PubChem Compound database."""

    ontology = PREFIX
    bioversions_key = "pubchem"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise, force=force)


def _get_cid_smiles_df(version: str) -> pd.DataFrame:
    url = _get_pubchem_extras_url(version, "CID-SMILES.gz")
    return ensure_df(PREFIX, url=url, version=version, dtype=str)


def get_pubchem_id_smiles_mapping(version: str) -> Mapping[str, str]:
    """Get a mapping from PubChem compound identifiers to SMILES strings."""
    df = _get_cid_smiles_df(version=version)
    return dict(df.values)


def get_pubchem_smiles_id_mapping(version: str) -> Mapping[str, str]:
    """Get a mapping from SMILES strings to PubChem compound identifiers."""
    df = _get_cid_smiles_df(version=version)
    return {v: k for k, v in df.values}


def get_pubchem_id_to_name(version: str) -> Mapping[str, str]:
    """Get a mapping from PubChem compound identifiers to their titles."""
    # 2 tab-separated columns: compound_id, name
    url = _get_pubchem_extras_url(version, "CID-Title.gz")
    df = ensure_df(PREFIX, url=url, version=version, dtype=str, encoding="latin-1")
    return dict(df.values)


def get_pubchem_id_to_mesh_id(version: str) -> Mapping[str, str]:
    """Get a mapping from PubChem compound identifiers to their equivalent MeSH terms."""
    url = _get_pubchem_extras_url(version, "CID-MeSH")
    df = ensure_df(
        PREFIX,
        url=url,
        version=version,
        dtype=str,
        header=None,
        name="CID-MeSH.tsv",
        names=["pubchem.compound_id", "mesh_id"],
    )
    mesh_name_to_id = get_name_id_mapping("mesh")
    needs_curation = set()
    mesh_ids = []
    for name in df["mesh_id"]:
        mesh_id = mesh_name_to_id.get(name)
        if mesh_id is None:
            if name not in needs_curation:
                needs_curation.add(name)
                logger.debug("[mesh] needs curating: %s", name)
        mesh_ids.append(mesh_id)
    logger.info("[mesh] %d/%d need updating", len(needs_curation), len(mesh_ids))
    df["mesh_id"] = mesh_ids
    return dict(df.values)


def _ensure_cid_name_path(*, version: str | None = None, force: bool = False) -> Path:
    if version is None:
        version = get_version("pubchem")
    # 2 tab-separated columns: compound_id, name
    cid_name_url = _get_pubchem_extras_url(version, "CID-Title.gz")
    cid_name_path = ensure_path(PREFIX, url=cid_name_url, version=version, force=force)
    return cid_name_path


def get_terms(*, version: str, use_tqdm: bool = True, force: bool = False) -> Iterable[Term]:
    """Get PubChem Compound terms."""
    cid_name_path = _ensure_cid_name_path(version=version, force=force)

    # 2 tab-separated columns: compound_id, synonym
    cid_synonyms_url = _get_pubchem_extras_url(version, "CID-Synonym-filtered.gz")
    cid_synonyms_path = ensure_path(PREFIX, url=cid_synonyms_url, version=version, force=force)

    it = iterate_gzips_together(cid_name_path, cid_synonyms_path)

    if use_tqdm:
        total = 146000000  # got this by reading the exports page
        it = tqdm(it, desc=f"mapping {PREFIX}", unit_scale=True, unit="compound", total=total)
    for identifier, name, raw_synonyms in it:
        reference = Reference(prefix=PREFIX, identifier=identifier, name=name)
        xrefs = []
        synonyms = []
        for synonym in raw_synonyms:
            if synonym.startswith("CHEBI:"):
                xrefs.append(Reference(prefix="chebi", identifier=removeprefix(synonym, "CHEBI:")))
            elif synonym.startswith("CHEMBL"):
                xrefs.append(Reference(prefix="chembl", identifier=synonym))
            elif synonym.startswith("InChI="):
                xrefs.append(Reference(prefix="inchi", identifier=synonym))
            # elif synonym.startswith("SCHEMBL"):
            #     xrefs.append(Reference(prefix="schembl", identifier=synonym))
            else:
                synonyms.append(Synonym(name=synonym))
            # TODO check other xrefs

        term = Term(
            reference=reference,
            synonyms=synonyms,
            xrefs=xrefs,
        )
        yield term


if __name__ == "__main__":
    PubChemCompoundGetter.cli()
