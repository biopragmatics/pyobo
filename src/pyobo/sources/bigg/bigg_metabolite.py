"""Converter for metabolites in BiGG."""

import logging
import re
from collections.abc import Iterable

import bioregistry
import pandas as pd
from pydantic import ValidationError
from tqdm import tqdm

from pyobo.sources.bigg.bigg_compartment import GO_MAPPING
from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import located_in, participates_in
from pyobo.utils.path import ensure_df

__all__ = [
    "BiGGMetaboliteGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "bigg.metabolite"
URL = "http://bigg.ucsd.edu/static/namespace/bigg_models_metabolites.txt"
PATTERN = re.compile("^[a-z_A-Z0-9]+$")

MOLECULE = Term.from_triple("cob", "0000013", "molecule")


class BiGGMetaboliteGetter(Obo):
    """An ontology representation of BiGG Metabolites."""

    ontology = PREFIX
    bioversions_key = "bigg"
    typedefs = [participates_in, located_in]
    root_terms = [MOLECULE.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_terms(force=force, version=self._version_or_raise)


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
    "MetaNetX (MNX) Equation": "metanetx.reaction",
    "RHEA": "rhea",
    "EC Number": "ec",
    "SEED Reaction": "seed.reaction",
    "Reactome Reaction": "reactome",
    "KEGG Reaction": "kegg.reaction",
}
EXACTS = {"inchikey"}


def _split(x) -> list[str]:
    if pd.notna(x):
        return [y.strip() for y in x.split(";")]
    return []


def iterate_terms(force: bool = False, version: str | None = None) -> Iterable[Term]:
    """Iterate terms for BiGG Metabolite."""
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

    universal_references: set[Reference] = set()
    compartment_references: set[Reference] = set()

    yield MOLECULE

    # TODO there are duplicates on universal ID - this might be
    # because the compartment ID is unique
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
        if not PATTERN.match(bigg_compartmental_id):
            tqdm.write(f"[{PREFIX}] invalid BIGG ID: {bigg_compartmental_id}")
            continue

        universal_name = name.strip() if pd.notna(name) else None

        _, _, compartment_letter = bigg_compartmental_id.rpartition("_")
        compartment_reference = GO_MAPPING[compartment_letter] or Reference(
            prefix="bigg.compartment", identifier=compartment_letter
        )
        compartment_references.add(compartment_reference)
        compartment_name = (
            f"{universal_name} (in {compartment_reference.name})" if universal_name else None
        )

        term = Term(
            reference=Reference(
                prefix=PREFIX,
                identifier=bigg_compartmental_id,
                name=compartment_name,
            ),
        )
        term.append_relationship(located_in, compartment_reference)

        if PATTERN.match(universal_bigg_id):
            universal_reference = Reference(
                prefix=PREFIX, identifier=universal_bigg_id, name=universal_name
            )
            term.append_parent(universal_reference)
            universal_references.add(universal_reference)
        else:
            tqdm.write(f"[{PREFIX}] invalid universal BIGG ID: {bigg_compartmental_id}")

        for old_bigg_id in _split(old_bigg_ids):
            if old_bigg_id in {bigg_compartmental_id, universal_bigg_id}:
                continue
            if not PATTERN.match(old_bigg_id):
                if not old_bigg_id.endswith("]"):
                    # if it ends with ']' then it's a compartment identifier
                    logger.debug(f"[{PREFIX}:{universal_bigg_id}] invalid alt ID: {old_bigg_id}")
                continue
            term.append_alt(Reference(prefix=PREFIX, identifier=old_bigg_id))
        _parse_model_links(term, model_list)
        _parse_dblinks(term, database_links)

        yield term

    for universal_reference in universal_references:
        yield Term(reference=universal_reference).append_parent(MOLECULE)

    for compartment in compartment_references:
        yield Term(reference=compartment)


def _parse_model_links(term: Term, model_list: str) -> None:
    for model_id in _split(model_list):
        try:
            reference = Reference(prefix="bigg.model", identifier=model_id)
        except ValidationError:
            tqdm.write(f"[{term.curie}] invalid model reference: {model_id}")
        else:
            term.annotate_object(participates_in, reference)


def _parse_dblinks(term: Term, database_links: str, property_map=None) -> None:
    if not property_map:
        property_map = {}

    # there are duplicate xrefs, keep track
    seen = set()

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
        elif identifier_url.startswith("http://identifiers.org/kegg.reaction/"):
            prefix = "kegg.reaction"
            identifier = identifier_url.removeprefix("http://identifiers.org/kegg.reaction/")
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
        if prefix == "rhea" and "#" in identifier:
            identifier = identifier.split("#")[0]

        try:
            reference = Reference(prefix=prefix, identifier=identifier)
        except ValidationError:
            tqdm.write(f"[{term.curie}] could not validate xref - {prefix}:{identifier}")
            continue
        # don't add self-reference
        if reference.pair == term.pair:
            continue

        if reference in seen:
            tqdm.write(f"[{term.curie}] got duplicate xref {reference}")
            continue

        seen.add(reference)

        if prefix in property_map:
            term.annotate_object(property_map[prefix], reference)
        elif prefix in EXACTS:
            term.append_exact_match(reference)
        else:
            term.append_xref(reference)


if __name__ == "__main__":
    BiGGMetaboliteGetter.cli()
