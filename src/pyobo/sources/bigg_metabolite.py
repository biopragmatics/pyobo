"""Converter for BIGG."""

from collections.abc import Iterable

import bioregistry
import pandas as pd
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import participates_in
from pyobo.utils.path import ensure_df

__all__ = [
    "BIGGMetaboliteGetter",
]

PREFIX = "bigg.metabolite"
URL = "http://bigg.ucsd.edu/static/namespace/bigg_models_metabolites.txt"


class BIGGMetaboliteGetter(Obo):
    """An ontology representation of BIGG Metabolites."""

    ontology = PREFIX
    bioversions_key = "bigg"
    dynamic_version = True
    typedefs = [participates_in]
    idspaces = {
        PREFIX: "http://bigg.ucsd.edu/models/universal/metabolites/",
        "bigg.model": "http://bigg.ucsd.edu/models/",
    }

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_terms(force=force)


KEY_TO_PREFIX = {
    "CHEBI": "chebi",
    "Human Metabolome Database": "hmdb",
    "LipidMaps": "lipidmaps",
    "BioCyc": "biocyc",
    "KEGG Compound": "kegg.compound",
    "MetaNetX (MNX) Chemical": "metanetx.chemical",
    "InChI Key": "inchikey",
    "SEED Compound": "seed.compound",
    "Reactome Compound": "reactome",
    "KEGG Drug": "kegg.drug",
    "KEGG Glycan": "kegg.glycan",
}
EXACTS = {"inchikey"}


def _split(x) -> list[str]:
    if pd.notna(x):
        return [y.strip() for y in x.split(";")]
    return []


def iterate_terms(force: bool = False, version: str | None = None) -> Iterable[Term]:
    """Iterate terms for BIGG Metabolite."""
    bigg_df = ensure_df(
        prefix=PREFIX,
        url=URL,
        force=force,
        version=version,
    )

    for v in KEY_TO_PREFIX.values():
        nmp = bioregistry.normalize_prefix(v)
        if v != nmp:
            raise ValueError(f"Normalize {v} to {nmp}")

    for (
        bigg_compartmental_id,
        universal_bigg_id,
        name,
        model_list,
        database_links,
        old_bigg_ids,
    ) in tqdm(
        bigg_df.values,
        unit_scale=True,
        unit="metabolite",
        desc=f"[{PREFIX}] processing",
    ):
        term = Term(
            reference=Reference(
                prefix=PREFIX, identifier=universal_bigg_id, name=name if pd.notna(name) else None
            ),
        )
        if pd.notna(bigg_compartmental_id):
            term.append_alt(Reference(prefix=PREFIX, identifier=bigg_compartmental_id))
        for old_bigg_id in _split(old_bigg_ids):
            if old_bigg_id in {bigg_compartmental_id, universal_bigg_id}:
                continue
            term.append_alt(Reference(prefix=PREFIX, identifier=old_bigg_id))
        for model_id in _split(model_list):
            term.annotate_object(
                participates_in, Reference(prefix="bigg.model", identifier=model_id)
            )

        for dblink in _split(database_links):
            key, _, identifier_url = dblink.strip().partition(":")
            identifier_url = identifier_url.strip()
            if not identifier_url:
                continue

            if identifier_url.startswith("http://identifiers.org/kegg.glycan/"):
                prefix = "kegg.glycan"
                identifier = identifier_url.removeprefix("http://identifiers.org/kegg.glycan/")
            elif identifier_url.startswith("http://identifiers.org/kegg.drug/"):
                prefix = "kegg.drug"
                identifier = identifier_url.removeprefix("http://identifiers.org/kegg.drug/")
            else:
                prefix_, identifier_ = bioregistry.parse_iri(identifier_url)
                if not prefix_ or not identifier_:
                    tqdm.write(f"[{PREFIX}] failed to parse xref IRI: {identifier_url}")
                    continue
                prefix, identifier = prefix_, identifier_
            if prefix == "kegg":
                prefix = "kegg.compound"
            if prefix != KEY_TO_PREFIX.get(key):
                tqdm.write(f"[{PREFIX}] mismatch between {prefix=} and {key=} - {identifier_url}")
                continue
            reference = Reference(prefix=prefix, identifier=identifier)
            if prefix in EXACTS:
                term.append_exact_match(reference)
            else:
                term.append_xref(reference)

        yield term


if __name__ == "__main__":
    BIGGMetaboliteGetter().write_default(force=True, write_obo=True)
