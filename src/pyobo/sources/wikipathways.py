"""Converter for WikiPathways."""

import logging
from collections.abc import Iterable

from pystow.utils import DownloadError
from tqdm import tqdm

from .gmt_utils import parse_wikipathways_gmt
from ..constants import SPECIES_REMAPPING
from ..struct import Obo, Reference, Term, from_species
from ..struct.typedef import has_participant
from ..utils.path import ensure_path

__all__ = [
    "WikiPathwaysGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "wikipathways"

ROOT = Reference(prefix="pw", identifier="0000001", name="pathway")
_PATHWAY_INFO = [
    ("Anopheles_gambiae", "7165"),
    ("Arabidopsis_thaliana", "3702"),
    ("Bos_taurus", "9913"),
    ("Caenorhabditis_elegans", "6239"),
    ("Canis_familiaris", "9615"),
    ("Danio_rerio", "7955"),
    ("Drosophila_melanogaster", "7227"),
    ("Equus_caballus", "9796"),
    ("Gallus_gallus", "9031"),
    ("Homo_sapiens", "9606"),
    ("Mus_musculus", "10090"),
    ("Oryza_sativa", "4530"),
    ("Pan_troglodytes", "9598"),
    ("Populus_trichocarpa", "3694"),
    ("Rattus_norvegicus", "10116"),
    ("Saccharomyces_cerevisiae", "4932"),
    ("Sus_scrofa", "9823"),
    ("Solanum_lycopersicum", "4081"),
]


class WikiPathwaysGetter(Obo):
    """An ontology representation of WikiPathways' pathway database."""

    ontology = bioversions_key = PREFIX
    typedefs = [from_species, has_participant]
    root_terms = [ROOT]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield Term(reference=ROOT)
        yield from iter_terms(version=self._version_or_raise)


def iter_terms(version: str) -> Iterable[Term]:
    """Get WikiPathways terms."""
    base_url = f"http://data.wikipathways.org/{version}/gmt/wikipathways-{version}-gmt"

    for species_code, taxonomy_id in tqdm(_PATHWAY_INFO, desc=f"[{PREFIX}]", unit="species"):
        url = f"{base_url}-{species_code}.gmt"
        try:
            path = ensure_path(PREFIX, url=url, version=version)
        except DownloadError as e:
            tqdm.write(f"[{PREFIX}] {e}")
            continue
        species_code = species_code.replace("_", " ")
        taxonomy_name = SPECIES_REMAPPING.get(species_code, species_code)

        for identifier, _version, _revision, name, _species, genes in parse_wikipathways_gmt(path):
            term = Term(reference=Reference(prefix=PREFIX, identifier=identifier, name=name))
            term.append_parent(ROOT)
            term.set_species(taxonomy_id, taxonomy_name)
            for ncbigene_id in genes:
                term.annotate_object(
                    has_participant,
                    Reference(prefix="ncbigene", identifier=ncbigene_id),
                )
            yield term


if __name__ == "__main__":
    WikiPathwaysGetter.cli()
