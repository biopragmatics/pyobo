"""Converter for NCI PID."""

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping

import pandas as pd

from ..api import get_id_name_mapping
from ..struct import Obo, Reference, Term
from ..struct.typedef import has_participant
from ..utils.ndex_utils import CX, ensure_ndex_network_set, iterate_aspect

__all__ = [
    "PIDGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "pid.pathway"
NDEX_NETWORK_SET_UUID = "8a2d7ee9-1513-11e9-bb6a-0ac135e8bacf"

# Unused, but maybe useful for later
URL = (
    "https://github.com/NCIP/pathway-interaction-database/raw/master/download/NCI-Pathway-Info.xlsx"
)


class PIDGetter(Obo):
    """An ontology representation of the NCI's Pathway Interaction Database."""

    ontology = PREFIX
    static_version = "1.0.0"
    typedefs = [has_participant]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def get_obo() -> Obo:
    """Get NCI PID as OBO."""
    return PIDGetter()


def iter_networks(use_tqdm: bool = False, force: bool = False) -> Iterable[tuple[str, CX]]:
    """Iterate over NCI PID networks."""
    yield from ensure_ndex_network_set(
        PREFIX, NDEX_NETWORK_SET_UUID, use_tqdm=use_tqdm, force=force
    )


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over NCI PID terms."""
    from protmapper.uniprot_client import get_gene_name, get_hgnc_id

    hgnc_id_to_name = get_id_name_mapping("hgnc")
    hgnc_name_to_id = {v: k for k, v in hgnc_id_to_name.items()}

    for uuid, cx in iter_networks(force=force, use_tqdm=True):
        name = None
        for node in iterate_aspect(cx, "networkAttributes"):
            if node["n"] == "name":
                name = node["v"]

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=uuid, name=name),
        )

        genes = set()
        for node in iterate_aspect(cx, "nodes"):
            name, reference = node["n"], node["r"]
            hgnc_id = hgnc_name_to_id.get(name)
            if hgnc_id:
                genes.add((hgnc_id, name))
            elif any(reference.startswith(x) for x in ("CHEBI:", "cas:")):
                pass
            elif reference.startswith("uniprot:"):
                uniprot_id = reference[len("uniprot:") :]
                hgnc_id = get_hgnc_id(uniprot_id)
                if hgnc_id is None:  # this only happens for proteins that seem to be virus related
                    # TODO reinvestigate this later
                    logger.debug(
                        "uniprot could not map %s/%s/%s to HGNC",
                        name,
                        reference,
                        get_gene_name(uniprot_id, web_fallback=False),
                    )
                else:
                    name = hgnc_id_to_name[hgnc_id]
                    genes.add((hgnc_id, name))
            else:
                logger.debug(f"unmapped: {name}, {reference}")

        for hgnc_id, hgnc_symbol in genes:
            term.append_relationship(
                has_participant, Reference(prefix="hgnc", identifier=hgnc_id, name=hgnc_symbol)
            )

        yield term


# TODO Update mappings based on curated sheet on google

MAPPINGS_SHEET = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vR7CuRJYBEGMobZQpjmzixL"
    "2bfWe4l4FRTySCSdQ_vwvkhpH_9rL4w1IMAe7ZkvhUcfCtQubVmRxqdW/pub?output=tsv"
)


def get_curation_df() -> pd.DataFrame:
    """Get the curated dataframe."""
    df = pd.read_csv(MAPPINGS_SHEET, sep="\t")
    df = df[df["Namespace"].notna()]
    return df[["Text from NDEx", "Type", "Namespace", "Identifier"]]


def get_remapping() -> Mapping[str, list[tuple[str, str]]]:
    """Get a mapping from text to list of HGNC id/symbols."""
    curation_df = get_curation_df()
    rv = defaultdict(list)
    for text, dtype, prefix, identifier in curation_df.values:
        if dtype == "protein":
            if prefix == "hgnc":
                rv[text] = [identifier]
                continue
        elif dtype == "protein family":
            if prefix == "fplx":
                logger.debug("unhandled - famplex protein family")
            elif prefix == "hgnc.genefamily":
                logger.debug("unhandled - HGNC gene family")
            else:
                logger.debug("unhandled prefix - %s", prefix)
        else:
            logger.debug("unhandled type - %s", dtype)

    return rv


if __name__ == "__main__":
    PIDGetter.cli()
