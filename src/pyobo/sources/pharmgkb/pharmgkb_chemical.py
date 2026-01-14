"""An ontology representation of PharmGKB chemicals."""

from collections.abc import Iterable

import pandas as pd
from tqdm import tqdm

from pyobo import Obo, Reference, Term, default_reference
from pyobo.sources.pharmgkb.utils import download_pharmgkb_tsv, split
from pyobo.struct.typedef import has_inchi, has_smiles

__all__ = [
    "PharmGKBChemicalGetter",
]

PREFIX = "pharmgkb.drug"
URL = "https://api.pharmgkb.org/v1/download/file/data/chemicals.zip"


class PharmGKBChemicalGetter(Obo):
    """An ontology representation of PharmGKB chemicals."""

    ontology = bioversions_key = PREFIX
    dynamic_version = True
    typedefs = [has_inchi, has_smiles]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


SKIP_PREFIXES = {"smiles", "inchi", "atc", "rxnorm", "pubchem.compound"}


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over terms."""
    df = download_pharmgkb_tsv(PREFIX, url=URL, inner="chemicals.tsv", force=force)

    type_to_ref = {
        typ: default_reference(PREFIX, typ.lower().replace(" ", "-").replace(",", ""), name=typ)
        for typ in df["Type"].unique()
    }
    for x in type_to_ref.values():
        yield Term(reference=x)

    for _, row in df.iterrows():
        term = Term.from_triple(PREFIX, identifier=row["PharmGKB Accession Id"], name=row["Name"])
        term.append_parent(type_to_ref[row["Type"]])
        if pd.notna(row["SMILES"]):
            term.annotate_string(has_smiles, row["SMILES"])
        if pd.notna(row["InChI"]):
            term.annotate_string(has_inchi, row["InChI"])
        for atc_id in split(row, "ATC Identifiers"):
            term.append_exact_match(Reference(prefix="atc", identifier=atc_id))
        for rxnorm_id in split(row, "RxNorm Identifiers"):
            if len(rxnorm_id) > 7:
                tqdm.write(f"invalid rxnorm luid (too long) - {rxnorm_id}")
            else:
                term.append_exact_match(Reference(prefix="rxnorm", identifier=rxnorm_id))
        for pubchem_id in split(row, "PubChem Compound Identifiers"):
            term.append_exact_match(Reference(prefix="pubchem.compound", identifier=pubchem_id))
        for xref_curie in split(row, "External Vocabulary"):
            try:
                reference = Reference.from_curie(xref_curie)
            except ValueError:
                pass
            else:
                if reference.prefix not in SKIP_PREFIXES:
                    term.append_exact_match(reference)
        for xref_curie in split(row, "Cross-references"):
            try:
                reference = Reference.from_curie(xref_curie)
            except ValueError:
                pass
            else:
                if reference.prefix not in SKIP_PREFIXES:
                    term.append_exact_match(reference)

        for trade_name in split(row, "Trade names"):
            # TODO use OMO term for trade name
            term.append_synonym(trade_name)

        # TODO add more

        yield term


if __name__ == "__main__":
    PharmGKBChemicalGetter.cli()
