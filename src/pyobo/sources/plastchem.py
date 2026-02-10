"""Import PlastChem."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo
from pyobo.struct import Reference, Term, default_reference
from pyobo.struct.typedef import has_canonical_smiles, has_inchi, has_isomeric_smiles
from pyobo.utils.path import ensure_path

__all__ = ["PlastChemGetter"]
PREFIX = "plastchem"
URL = "https://zenodo.org/records/10701706/files/plastchem_db_v1.0.xlsx?download=1"

LISTS = [
    "Red",
    "Orange",
    "Watch",
    "White",
    "Grey",
    "MEA",
]

LIST_TERM = default_reference(PREFIX, "list")
XX = {f"{listn}_list": default_reference(PREFIX, f"{listn}_list") for listn in LISTS}


class PlastChemGetter(Obo):
    """An ontology representation of PlastChem."""

    ontology = PREFIX
    static_version = "1.0"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Do it."""
    yield Term(reference=LIST_TERM)
    for r in XX.values():
        term = Term(reference=r)
        term.append_parent(LIST_TERM)
        yield term

    path = ensure_path(PREFIX, url=URL)
    df = pd.read_excel(path, sheet_name="Full database", dtype=str, skiprows=1)
    for _, row in df.iterrows():
        if pd.isna(row["plastchem_ID"]):
            continue

        if pd.notna(row["pubchem_name"]):
            name = row["pubchem_name"]
        elif pd.notna(row["iupac_name"]):
            name = row["iupac_name"]
        else:
            name = None
        term = Term.from_triple(PREFIX, row["plastchem_ID"], name)

        cas = row.pop("cas")
        cas_fixed = row.pop("cas_fixed")
        if pd.notna(cas_fixed) and pd.notna(cas):
            if cas != cas_fixed.lstrip("'"):
                pass
            term.append_exact_match(Reference(prefix="cas", identifier=cas))

        if pd.notna(pubchem_id := row.pop("pubchem_cid")):
            term.append_exact_match(Reference(prefix="pubchem", identifier=pubchem_id))

        if pd.notna(canonical_smiles := row.pop("canonical_smiles")):
            term.annotate_string(has_canonical_smiles, canonical_smiles)
        if pd.notna(isomeric_smiles := row.pop("isomeric_smiles")):
            term.annotate_string(has_isomeric_smiles, isomeric_smiles)
        if pd.notna(inchi := row.pop("inchi")):
            term.annotate_string(has_inchi, inchi)
        if pd.notna(inchikey := row.pop("inchikey")):
            term.append_exact_match(Reference(prefix="inchikey", identifier=inchikey))

        # TODO ECHA_grouping
        # TODO ground to chebi:
        #  - Harmonized_functions
        #  - original_function_plasticmap
        #  - original_function_cpp
        #  - original_primary_function_aurisano
        #  - original_other_function_aurisano
        #  - industrial_sector_plasticmap

        yield term


if __name__ == "__main__":
    PlastChemGetter.cli()
