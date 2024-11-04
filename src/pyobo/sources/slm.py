"""Swisslipids."""

from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo import Obo, Reference, Term
from pyobo.struct.struct import abbreviation as abbreviation_typedef
from pyobo.struct.typedef import exact_match, has_inchi, has_smiles
from pyobo.utils.path import ensure_df

__all__ = [
    "SLMGetter",
]

PREFIX = "slm"
COLUMNS = [
    "Lipid ID",
    "Level",
    "Name",
    "Abbreviation*",
    "Synonyms*",
    "Lipid class*",
    "Parent",
    "Components*",
    "SMILES (pH7.3)",
    "InChI (pH7.3)",
    "InChI key (pH7.3)",
    # "Formula (pH7.3)", "Charge (pH7.3)", "Mass (pH7.3)",
    # "Exact Mass (neutral form)", "Exact m/z of [M.]+", "Exact m/z of [M+H]+", "Exact m/z of [M+K]+ ",
    # "Exact m/z of [M+Na]+", "Exact m/z of [M+Li]+", "Exact m/z of [M+NH4]+", "Exact m/z of [M-H]-",
    # "Exact m/z of [M+Cl]-", "Exact m/z of [M+OAc]- ",
    "CHEBI",
    "LIPID MAPS",
    "HMDB",
    "PMID",
]


class SLMGetter(Obo):
    """An ontology representation of SwissLipid's lipid nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [exact_match]
    synonym_typedefs = [abbreviation_typedef]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get SwissLipids as OBO."""
    return SLMGetter(force=force)


def iter_terms(version: str, force: bool = False):
    """Iterate over SwissLipids terms."""
    df = ensure_df(
        prefix=PREFIX,
        url="https://www.swisslipids.org/api/file.php?cas=download_files&file=lipids.tsv",
        version=version,
        name="lipids.tsv.gz",
        encoding="cp1252",
        force=force,
    )
    for (
        identifier,
        level,
        name,
        abbreviation,
        synonyms,
        _cls,
        _parent,
        _components,
        smiles,
        inchi,
        inchikey,
        chebi_ids,
        lipidmaps_ids,
        hmdb_ids,
        pubmed_ids,
    ) in tqdm(
        df[COLUMNS].values, desc=f"[{PREFIX}] generating terms", unit_scale=True, unit="lipid"
    ):
        if identifier.startswith("SLM:"):
            identifier = identifier[len("SLM:") :]
        else:
            raise ValueError(identifier)
        term = Term.from_triple(PREFIX, identifier, name)
        if pd.notna(level):
            term.append_property("level", level)
        if pd.notna(abbreviation):
            term.append_synonym(abbreviation, type=abbreviation_typedef)
        if pd.notna(synonyms):
            for synonym in synonyms.split("|"):
                term.append_synonym(synonym.strip())
        if pd.notna(smiles):
            term.append_property(has_smiles, smiles)
        if pd.notna(inchi) and inchi != "InChI=none":
            if inchi.startswith("InChI="):
                inchi = inchi[len("InChI=") :]
            term.append_property(has_inchi, inchi)
        if pd.notna(inchikey):
            inchikey = inchikey.removeprefix("InChIKey=").strip()
            if inchikey and inchikey != "none":
                try:
                    inchi_ref = Reference(prefix="inchikey", identifier=inchikey)
                except ValueError:
                    tqdm.write(
                        f"[slm:{identifier}] had invalid inchikey reference: ({type(inchikey)}) {inchikey}"
                    )
                else:
                    term.append_exact_match(inchi_ref)
        for chebi_id in _split(chebi_ids):
            term.append_xref(("chebi", chebi_id))
        for lipidmaps_id in _split(lipidmaps_ids):
            term.append_exact_match(("lipidmaps", lipidmaps_id))
        for hmdb_id in _split(hmdb_ids):
            term.append_exact_match(("hmdb", hmdb_id))
        for pubmed_id in _split(pubmed_ids):
            term.append_provenance(("pubmed", pubmed_id))
        # TODO how to handle class, parents, and components?
        yield term


def _split(s: str) -> Iterable[str]:
    if pd.notna(s):
        for x in s.split("|"):
            x = x.strip()
            if x:
                yield x


if __name__ == "__main__":
    get_obo().write_default(write_obo=True, use_tqdm=True)
