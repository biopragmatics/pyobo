"""API utilities for KEGG."""

import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pyobo import Reference, Term, ensure_path
from pyobo.struct import from_species
from pyobo.utils.path import ensure_df, prefix_directory_join

KEGG_GENES_PREFIX = "kegg.genes"
KEGG_GENOME_PREFIX = "kegg.genome"
KEGG_PATHWAY_PREFIX = "kegg.pathway"

BASE = "http://rest.kegg.jp"
SKIP = {
    "T03333",
    "T03334",
    "T03356",
    "T03357",
    "T03358",
    "T03359",
}


@dataclass
class KEGGGenome:
    """A data structure for a parsed line of the KEGG Genomes list."""

    identifier: str
    name: str
    code: str | None
    long_code: str | None
    taxonomy_id: str | None

    def annotate_term(self, term: Term) -> None:
        """Annotate the term with the species represented by this object."""
        term.append_relationship(
            from_species,
            self.get_reference(),
        )
        if self.taxonomy_id is not None:
            term.set_species(self.taxonomy_id)

    def get_reference(self) -> Reference:
        """Get the reference for this genome."""
        return Reference(
            prefix="kegg.genome",
            identifier=self.identifier,
            name=self.name,
        )


def ensure_list_genomes(version: str) -> Path:
    """Ensure the KEGG Genome file is downloaded."""
    return ensure_path(
        KEGG_GENOME_PREFIX,
        url=f"{BASE}/list/genome",
        name="genome.tsv",
        version=version,
    )


def ensure_list_pathways(version: str) -> Mapping[str, str]:
    """Ensure the KEGG Map (non species specific)."""
    rv = ensure_df(
        KEGG_PATHWAY_PREFIX,
        url=f"{BASE}/list/pathway",
        name="pathway.tsv",
        version=version,
    )
    return {k[len("path:") :]: v for k, v in rv.values}


"""GENOME SPECIFIC"""


def ensure_list_genome(kegg_genome_id: str, *, version: str) -> Path:
    """Get the list of genes for the given organism."""
    return ensure_path(
        KEGG_GENES_PREFIX,
        "genes",
        url=f"{BASE}/list/{kegg_genome_id}",
        name=f"{kegg_genome_id}.tsv",
        version=version,
    )


def ensure_conv_genome_uniprot(kegg_genome_id: str, *, version: str) -> Path | None:
    """Get the KEGG-UniProt protein map for the given organism."""
    return _ensure_conv_genome_helper(kegg_genome_id, "uniprot", version=version)


def ensure_conv_genome_ncbigene(kegg_genome_id: str, *, version: str) -> Path | None:
    """Get the KEGG-NCBIGENE protein map for the given organism."""
    return _ensure_conv_genome_helper(kegg_genome_id, "ncbi-geneid", version=version)


def _ensure_conv_genome_helper(
    kegg_genome_id: str,
    target_database: str,
    *,
    version: str,
) -> Path | None:
    """Get the KEGG-external protein map for the given organism/database."""
    name = f"{kegg_genome_id}.tsv"
    try:
        rv = ensure_path(
            KEGG_GENES_PREFIX,
            f"conv_{target_database}",
            url=f"{BASE}/conv/{target_database}/{kegg_genome_id}",
            name=name,
            version=version,
        )
    except urllib.error.HTTPError:
        path_rv = prefix_directory_join(
            KEGG_GENES_PREFIX,
            f"conv_{target_database}",
            name=name,
            version=version,
        )
        with path_rv.open("w") as file:
            print(file=file)
        return path_rv
    except FileNotFoundError:
        return None
    else:
        return rv


def ensure_link_pathway_genome(kegg_genome_id: str, *, version: str) -> Path:
    """Get the protein-pathway links for the given organism."""
    return ensure_path(
        KEGG_PATHWAY_PREFIX,
        "link_pathway",
        url=f"{BASE}/link/pathway/{kegg_genome_id}",
        name=f"{kegg_genome_id}.tsv",
        version=version,
    )


def ensure_list_pathway_genome(kegg_genome_id: str, *, version: str) -> Path:
    """Get the list of pathways for the given organism."""
    return ensure_path(
        KEGG_PATHWAY_PREFIX,
        "pathways",
        url=f"{BASE}/list/pathway/{kegg_genome_id}",
        name=f"{kegg_genome_id}.tsv",
        version=version,
    )
