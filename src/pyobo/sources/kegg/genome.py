# -*- coding: utf-8 -*-

"""Convert KEGG Genome to OBO.

Run with ``python -m pyobo.sources.kegg.genome``
"""

import logging
from typing import Iterable

import bioversions
import click
from more_click import verbose_option
from tqdm import tqdm

import pyobo
from pyobo.sources.kegg.api import KEGGGenome, KEGG_GENOME_PREFIX, SKIP, ensure_list_genomes
from pyobo.struct import Obo, Reference, Term

logger = logging.getLogger(__name__)


def _s(line: str, sep: str):
    return [part.strip() for part in line.strip().split(sep, 1)]


def get_obo() -> Obo:
    """Get KEGG Genome as OBO."""
    version = bioversions.get_version("kegg")
    return Obo(
        ontology=KEGG_GENOME_PREFIX,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        name="KEGG Genome",
        data_version=version,
        auto_generated_by=f"bio2obo:{KEGG_GENOME_PREFIX}",
    )


def parse_genome_line(line: str) -> KEGGGenome:
    """Parse a line from the KEGG Genome database."""
    line = line.strip()
    identifier, rest = _s(line, "\t")
    identifier = identifier[len("gn:") :]
    if ";" in rest:
        rest, name = _s(rest, ";")

        rest = [part.strip() for part in rest.split(",")]
        if len(rest) == 3:
            kegg_code, long_code, taxonomy_id = rest
        elif len(rest) == 2:
            kegg_code, taxonomy_id = rest
            long_code = None
        else:
            raise ValueError
    else:
        name = rest
        taxonomy_id = None
        long_code = None
        kegg_code = None

    if "\t" in name:
        logger.warning("[%s] tab in name: %s", KEGG_GENOME_PREFIX, name)
        name = name.replace("\t", " ")

    return KEGGGenome(
        identifier=identifier,
        code=kegg_code,
        long_code=long_code,
        taxonomy_id=taxonomy_id,
        name=name,
    )


def iter_kegg_genomes(version: str, desc: str) -> Iterable[KEGGGenome]:
    """Iterate over all KEGG genomes."""
    path = ensure_list_genomes(version=version)
    with open(path) as file:
        lines = [line.strip() for line in file]
    it = tqdm(lines, desc=desc)
    for line in it:
        yv = parse_genome_line(line)
        it.set_postfix({"id": yv.identifier, "name": yv.name})
        yield yv


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over terms for KEGG Genome."""
    errors = 0
    for kegg_genome in iter_kegg_genomes(version=version, desc="KEGG Genomes"):
        if kegg_genome.identifier in SKIP:
            continue
        term = Term.from_triple(
            prefix=KEGG_GENOME_PREFIX,
            identifier=kegg_genome.identifier,
            name=kegg_genome.name,
        )
        if kegg_genome.taxonomy_id is not None:
            taxonomy_name = pyobo.get_name("ncbitaxon", kegg_genome.taxonomy_id)
            if taxonomy_name is None:
                errors += 1
                logger.debug(
                    f"[{KEGG_GENOME_PREFIX}] could not find name for taxonomy:{kegg_genome.taxonomy_id}"
                )
            term.append_xref(
                Reference(
                    prefix="ncbitaxon",
                    identifier=kegg_genome.taxonomy_id,
                    name=taxonomy_name,
                )
            )
        yield term

    logger.info("[%s] unable to find %d taxonomy names in NCBI", KEGG_GENOME_PREFIX, errors)


@click.command()
@verbose_option
def _main():
    get_obo().write_default()


if __name__ == "__main__":
    _main()
