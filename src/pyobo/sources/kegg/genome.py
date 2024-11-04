"""Convert KEGG Genome to OBO.

Run with ``python -m pyobo.sources.kegg.genome``
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from tqdm.auto import tqdm

from pyobo.constants import NCBITAXON_PREFIX
from pyobo.resources.ncbitaxon import get_ncbitaxon_name
from pyobo.sources.kegg.api import (
    KEGG_GENOME_PREFIX,
    SKIP,
    KEGGGenome,
    ensure_list_genomes,
)
from pyobo.struct import Obo, Reference, Term

__all__ = [
    "KEGGGenomeGetter",
]

logger = logging.getLogger(__name__)


def _s(line: str, sep: str):
    return [part.strip() for part in line.strip().split(sep, 1)]


class KEGGGenomeGetter(Obo):
    """An ontology representation of KEGG Genomes."""

    ontology = KEGG_GENOME_PREFIX
    bioversions_key = "kegg"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def get_obo() -> Obo:
    """Get KEGG Genome as OBO."""
    # since old kegg versions go away forever, do NOT add a force option
    return KEGGGenomeGetter()


def parse_genome_line(line: str) -> KEGGGenome | None:
    """Parse a line from the KEGG Genome database."""
    if not line.startswith("T"):
        #  This is for an NCBI Taxonomy
        return None
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
        elif len(rest) == 1:
            (kegg_code,) = rest
            long_code, taxonomy_id = None, None
        else:
            raise ValueError(f"unexpected line: {line}")
    else:
        name = rest
        taxonomy_id = None
        long_code = None
        kegg_code = None

    if "\t" in name:
        # TODO maybe throw this out?
        tqdm.write(f"[{KEGG_GENOME_PREFIX}] tab in name: {name}")
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
    # since old kegg versions go away forever, do NOT add a force option
    path = ensure_list_genomes(version=version)
    with open(path) as file:
        lines = [line.strip() for line in file]
    it = tqdm(lines, desc=desc, unit_scale=True, unit="genome")
    for line in it:
        yv = parse_genome_line(line)
        if yv is None:
            continue
        it.set_postfix({"id": yv.identifier, "name": yv.name})
        yield yv


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over terms for KEGG Genome."""
    # since old kegg versions go away forever, do NOT add a force option
    errors = 0
    for kegg_genome in iter_kegg_genomes(version=version, desc="KEGG Genomes"):
        if kegg_genome.identifier in SKIP:
            continue

        try:
            reference = Reference(
                prefix=KEGG_GENOME_PREFIX, identifier=kegg_genome.identifier, name=kegg_genome.name
            )
        except ValueError:
            tqdm.write(f"[{KEGG_GENOME_PREFIX}] invalid identifier: {kegg_genome}")
            continue

        term = Term(reference=reference)
        if kegg_genome.taxonomy_id is not None:
            taxonomy_name = get_ncbitaxon_name(kegg_genome.taxonomy_id)
            if taxonomy_name is None:
                errors += 1
                logger.debug(
                    f"[{KEGG_GENOME_PREFIX}] could not find name for taxonomy:{kegg_genome.taxonomy_id}"
                )
            term.append_xref(
                Reference(
                    prefix=NCBITAXON_PREFIX,
                    identifier=kegg_genome.taxonomy_id,
                    name=taxonomy_name,
                )
            )
        yield term

    if errors:
        logger.info("[%s] unable to find %d taxonomy names in NCBI", KEGG_GENOME_PREFIX, errors)


if __name__ == "__main__":
    KEGGGenomeGetter.cli()
