# -*- coding: utf-8 -*-

"""API utilities for KEGG."""

import urllib.error
from dataclasses import dataclass
from typing import Mapping, Optional

from pyobo import Reference, Term, TypeDef, ensure_path
from pyobo.path_utils import ensure_df

KEGG_GENES_PREFIX = 'kegg.genes'
KEGG_GENOME_PREFIX = 'kegg.genome'
KEGG_PATHWAY_PREFIX = 'kegg.pathway'

BASE = 'http://rest.kegg.jp'

from_kegg_species = TypeDef(
    reference=Reference.default('inKeggTaxon', 'in KEGG taxon'),
)


@dataclass
class KEGGGenome:
    """A data structure for a parsed line of the KEGG Genomes list."""

    identifier: str
    name: str
    code: Optional[str]
    long_code: Optional[str]
    taxonomy_id: Optional[str]

    def annotate_term(self, term: Term) -> None:
        """Annotate the term with the species represented by this object."""
        term.append_relationship(
            from_kegg_species,
            self.get_reference(),
        )
        if self.taxonomy_id is not None:
            term.set_species(self.taxonomy_id)

    def get_reference(self) -> Reference:
        """Get the reference for this genome."""
        return Reference(
            prefix='kegg.genome',
            identifier=self.identifier,
            name=self.name,
        )


def ensure_list_genomes() -> str:
    """Ensure the KEGG Genome file is downloaded."""
    return ensure_path(
        KEGG_GENOME_PREFIX,
        url=f'{BASE}/list/genome',
        path='genome.tsv',
    )


def ensure_list_pathways() -> Mapping[str, str]:
    """Ensure the KEGG Map (non species specific)."""
    rv = ensure_df(
        KEGG_PATHWAY_PREFIX,
        url=f'{BASE}/list/pathway',
        path='pathway.tsv',
    )
    return {
        k[len('path:'):]: v
        for k, v in rv.values
    }


"""GENOME SPECIFIC"""


def ensure_list_genome(kegg_genome_id: str) -> str:
    """Get the list of genes for the given organism."""
    return ensure_path(
        KEGG_GENES_PREFIX,
        'genes',
        url=f'{BASE}/list/{kegg_genome_id}',
        path=f'{kegg_genome_id}.tsv',
    )


def ensure_conv_genome_uniprot(kegg_genome_id: str, error_on_missing: bool = False) -> Optional[str]:
    """Get the KEGG-UniProt protein map for the given organism."""
    return _ensure_conv_genome_helper(kegg_genome_id, 'uniprot', error_on_missing=error_on_missing)


def ensure_conv_genome_ncbigene(kegg_genome_id: str, error_on_missing: bool = False) -> Optional[str]:
    """Get the KEGG-NCBIGENE protein map for the given organism."""
    return _ensure_conv_genome_helper(kegg_genome_id, 'ncbi-geneid', error_on_missing=error_on_missing)


def _ensure_conv_genome_helper(
    kegg_genome_id: str,
    target_database: str,
    error_on_missing: bool = False,
) -> Optional[str]:
    """Get the KEGG-external protein map for the given organism/database."""
    try:
        rv = ensure_path(
            KEGG_GENES_PREFIX,
            f'conv_{target_database}',
            url=f'{BASE}/conv/{target_database}/{kegg_genome_id}',
            path=f'{kegg_genome_id}.tsv',
            error_on_missing=error_on_missing,
        )
    except urllib.error.HTTPError:
        return None
    except FileNotFoundError:
        return None
    else:
        return rv


def ensure_link_pathway_genome(kegg_genome_id: str, error_on_missing: bool = False) -> str:
    """Get the protein-pathway links for the given organism.

    :raises: FileNotFoundError
    """
    return ensure_path(
        KEGG_PATHWAY_PREFIX,
        'link_pathway',
        url=f'{BASE}/link/pathway/{kegg_genome_id}',
        path=f'{kegg_genome_id}.tsv',
        error_on_missing=error_on_missing,
    )


def ensure_list_pathway_genome(kegg_genome_id: str, error_on_missing: bool = False) -> str:
    """Get the list of pathways for the given organism.

    :raises: FileNotFoundError
    """
    return ensure_path(
        KEGG_PATHWAY_PREFIX,
        'pathways',
        url=f'{BASE}/list/pathway/{kegg_genome_id}',
        path=f'{kegg_genome_id}.txt',  # TODO rename to .tsv
        error_on_missing=error_on_missing,
    )
