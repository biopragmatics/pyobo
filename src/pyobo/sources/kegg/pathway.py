"""Convert KEGG Pathways to OBO.

Run with ``python -m pyobo.sources.kegg.pathway``
"""

import logging
import urllib.error
from collections import defaultdict
from collections.abc import Iterable, Mapping
from functools import partial
from typing import Union

from tqdm.auto import tqdm
from tqdm.contrib.concurrent import thread_map
from tqdm.contrib.logging import logging_redirect_tqdm

from pyobo.sources.kegg.api import (
    KEGG_GENES_PREFIX,
    KEGG_PATHWAY_PREFIX,
    KEGGGenome,
    ensure_link_pathway_genome,
    ensure_list_pathway_genome,
    ensure_list_pathways,
)
from pyobo.sources.kegg.genome import iter_kegg_genomes
from pyobo.struct import (
    Obo,
    Reference,
    Term,
    from_species,
    has_participant,
    species_specific,
)

__all__ = [
    "KEGGPathwayGetter",
]

logger = logging.getLogger(__name__)


class KEGGPathwayGetter(Obo):
    """An ontology representation of KEGG Pathways."""

    ontology = KEGG_PATHWAY_PREFIX
    bioversions_key = "kegg"
    typedefs = [from_species, species_specific, has_participant]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def get_obo() -> Obo:
    """Get KEGG Pathways as OBO."""
    # since old kegg versions go away forever, do NOT add a force option
    return KEGGPathwayGetter()


def iter_terms(version: str, skip_missing: bool = True) -> Iterable[Term]:
    """Iterate over terms for KEGG Pathway."""
    # since old kegg versions go away forever, do NOT add a force option
    yield from _iter_map_terms(version=version)
    it = iter_kegg_pathway_paths(version=version, skip_missing=skip_missing)
    for row in tqdm(it, unit_scale=True, unit="genome", desc="Parsing genomes"):
        if not row:
            continue
        kegg_genome, list_pathway_path, link_pathway_path = row
        if not kegg_genome or not list_pathway_path or not link_pathway_path:
            continue
        yield from _iter_genome_terms(
            list_pathway_path=list_pathway_path,
            link_pathway_path=link_pathway_path,
            kegg_genome=kegg_genome,
        )


def _get_link_pathway_map(path: str) -> Mapping[str, list[str]]:
    rv = defaultdict(list)
    with open(path) as file:
        for line in file:
            try:
                protein_id, pathway_id = line.strip().split("\t")
            except ValueError:
                logger.warning("Unable to parse link file line: %s", line)
            else:
                rv[pathway_id[len("path:") :]].append(protein_id)

    return {pathway_id: sorted(protein_ids) for pathway_id, protein_ids in rv.items()}


def _iter_map_terms(version: str) -> Iterable[Term]:
    for identifier, name in ensure_list_pathways(version=version).items():
        yield Term.from_triple(
            prefix=KEGG_PATHWAY_PREFIX,
            identifier=identifier,
            name=name,
        )


def _iter_genome_terms(
    *,
    list_pathway_path: str,
    link_pathway_path: str,
    kegg_genome: KEGGGenome,
) -> Iterable[Term]:
    terms = {}
    with open(list_pathway_path) as file:
        list_pathway_lines = [line.strip() for line in file]
    for line in list_pathway_lines:
        line = line.strip()
        pathway_id, name = (part.strip() for part in line.split("\t"))
        pathway_id = pathway_id[len("path:") :]

        terms[pathway_id] = term = Term.from_triple(
            prefix=KEGG_PATHWAY_PREFIX,
            identifier=pathway_id,
            name=name,
        )

        # Annotate species information
        kegg_genome.annotate_term(term)

        # Annotate the non-species specific code
        _start = min(i for i, e in enumerate(pathway_id) if e.isnumeric())
        pathway_code = pathway_id[_start:]
        term.append_relationship(
            species_specific,
            Reference(prefix=KEGG_PATHWAY_PREFIX, identifier=f"map{pathway_code}"),
        )

    for pathway_id, protein_ids in _get_link_pathway_map(link_pathway_path).items():
        pathway_term = terms.get(pathway_id)
        if pathway_term is None:
            tqdm.write(f"could not find kegg.pathway:{pathway_id} for {kegg_genome.name}")
            continue
        for protein_id in protein_ids:
            pathway_term.append_relationship(
                has_participant,
                Reference(
                    prefix=KEGG_GENES_PREFIX,
                    identifier=protein_id,
                ),
            )

    yield from terms.values()


def iter_kegg_pathway_paths(
    version: str, skip_missing: bool = True
) -> Iterable[Union[tuple[KEGGGenome, str, str], tuple[None, None, None]]]:
    """Get paths for the KEGG Pathway files."""
    genomes = list(iter_kegg_genomes(version=version, desc="KEGG Pathways"))
    func = partial(_process_genome, version=version, skip_missing=skip_missing)
    return thread_map(func, genomes, unit="pathway", unit_scale=True)


def _process_genome(kegg_genome, version, skip_missing):
    with logging_redirect_tqdm():
        try:
            list_pathway_path = ensure_list_pathway_genome(
                kegg_genome.identifier,
                version=version,
                error_on_missing=not skip_missing,
            )
            link_pathway_path = ensure_link_pathway_genome(
                kegg_genome.identifier,
                version=version,
                error_on_missing=not skip_missing,
            )
        except urllib.error.HTTPError as e:
            code = e.getcode()
            if code != 404:
                msg = (
                    f"[HTTP {code}] Error downloading {kegg_genome.identifier} ({kegg_genome.name}"
                )
                if kegg_genome.taxonomy_id is None:
                    msg = f"{msg}): {e.geturl()}"
                else:
                    msg = f"{msg}; taxonomy:{kegg_genome.taxonomy_id}): {e.geturl()}"
                tqdm.write(msg)
        except FileNotFoundError:
            return None, None, None
        else:
            return kegg_genome, list_pathway_path, link_pathway_path


if __name__ == "__main__":
    KEGGPathwayGetter.cli()
