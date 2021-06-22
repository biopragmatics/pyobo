# -*- coding: utf-8 -*-

"""Convert KEGG Pathways to OBO.

Run with ``python -m pyobo.sources.kegg.pathway``
"""

import logging
import urllib.error
from collections import defaultdict
from typing import Iterable, List, Mapping, Tuple

import bioversions
import click
from more_click import verbose_option
from tqdm import tqdm

from pyobo.sources.kegg.api import (
    KEGGGenome,
    KEGG_GENES_PREFIX,
    KEGG_PATHWAY_PREFIX,
    ensure_link_pathway_genome,
    ensure_list_pathway_genome,
    ensure_list_pathways,
    from_kegg_species,
)
from pyobo.sources.kegg.genome import iter_kegg_genomes
from pyobo.struct import Obo, Reference, Term, from_species, has_part, species_specific

logger = logging.getLogger(__name__)


def get_obo(skip_missing: bool = True) -> Obo:
    """Get KEGG Pathways as OBO."""
    version = bioversions.get_version("kegg")
    return Obo(
        ontology=KEGG_PATHWAY_PREFIX,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(skip_missing=skip_missing, version=version),
        name="KEGG Pathways",
        typedefs=[from_kegg_species, from_species, species_specific, has_part],
        auto_generated_by=f"bio2obo:{KEGG_PATHWAY_PREFIX}",
        data_version=version,
    )


def iter_terms(version: str, skip_missing: bool = True) -> Iterable[Term]:
    """Iterate over terms for KEGG Pathway."""
    yield from _iter_map_terms(version=version)
    it = iter_kegg_pathway_paths(version=version, skip_missing=skip_missing)
    for kegg_genome, list_pathway_path, link_pathway_path in it:
        yield from _iter_genome_terms(
            list_pathway_path=list_pathway_path,
            link_pathway_path=link_pathway_path,
            kegg_genome=kegg_genome,
        )


def _get_link_pathway_map(path: str) -> Mapping[str, List[str]]:
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
        pathway_id, name = [part.strip() for part in line.split("\t")]
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
        term = terms.get(pathway_id)
        if term is None:
            tqdm.write(f"could not find kegg.pathway:{pathway_id} for {kegg_genome.name}")
            continue
        for protein_id in protein_ids:
            term.append_relationship(
                has_part,
                Reference(
                    prefix=KEGG_GENES_PREFIX,
                    identifier=protein_id,
                ),
            )

    yield from terms.values()


def iter_kegg_pathway_paths(
    version: str, skip_missing: bool = True
) -> Iterable[Tuple[KEGGGenome, str, str]]:
    """Get paths for the KEGG Pathway files."""
    for kegg_genome in iter_kegg_genomes(version=version, desc="KEGG Pathways"):
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
            continue
        else:
            yield kegg_genome, list_pathway_path, link_pathway_path


@click.command()
@verbose_option
@click.option("--skip-missing", is_flag=True)
def _main(skip_missing: bool):
    get_obo(skip_missing=skip_missing).write_default()


if __name__ == "__main__":
    _main()
