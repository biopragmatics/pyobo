"""Converter for WikiPathways."""

import logging
from collections.abc import Iterable

import pystow
from pystow.utils import DownloadError, read_zipfile_rdf
from tqdm import tqdm

from .gmt_utils import parse_wikipathways_gmt
from ..constants import SPECIES_REMAPPING
from ..struct import Obo, Reference, Term, from_species
from ..struct.typedef import contributes_to_condition, has_depiction, has_participant, located_in
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
    typedefs = [from_species, has_participant, contributes_to_condition, located_in, has_depiction]
    root_terms = [ROOT]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield Term(reference=ROOT)
        yield from iter_terms(version=self._version_or_raise)


PW_PREFIX = "http://purl.obolibrary.org/obo/PW_"
DOID_PREFIX = "http://purl.obolibrary.org/obo/DOID_"
CL_PREFIX = "http://purl.obolibrary.org/obo/CL_"


def iter_terms(version: str, *, include_descriptions: bool = False) -> Iterable[Term]:
    """Get WikiPathways terms."""
    archive_url = f"https://data.wikipathways.org/current/rdf/wikipathways-{version}-rdf-wp.zip"
    archive = pystow.ensure(PREFIX, url=archive_url, version=version)

    base_url = f"http://data.wikipathways.org/{version}/gmt/wikipathways-{version}-gmt"
    pw_references = set()
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
            graph = read_zipfile_rdf(archive, inner_path=f"wp/{identifier}.ttl")
            uri = f"https://identifiers.org/wikipathways/{identifier}"

            definition: str | None = None
            if include_descriptions:
                # TODO deal with weird characters breaking OFN
                description_results = list(
                    graph.query(
                        f"SELECT ?p WHERE {{ <{uri}> pav:hasVersion/dcterms:description ?p }} LIMIT 1"
                    )
                )
                if description_results:
                    definition = str(description_results[0][0])  # type:ignore[index]

            term = Term(
                reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
                definition=definition,
            )
            term.set_species(taxonomy_id, taxonomy_name)
            term.annotate_uri(
                has_depiction,
                f"https://www.wikipathways.org/wikipathways-assets/pathways/{identifier}/{identifier}.svg",
            )
            for ncbigene_id in genes:
                term.annotate_object(
                    has_participant,
                    Reference(prefix="ncbigene", identifier=ncbigene_id),
                )
            # TODO switch query over to including chemicals from RDF SPARQL query
            # TODO get description from SPARQL
            parents = [  # type:ignore[misc]
                p
                for (p,) in graph.query(
                    f"SELECT ?p WHERE {{ <{uri}> pav:hasVersion/wp:pathwayOntologyTag ?p }}"
                )
            ]
            for parent in parents:
                if parent.startswith(PW_PREFIX):
                    ref = Reference(prefix="pw", identifier=parent.removeprefix(PW_PREFIX))
                    pw_references.add(ref)
                    term.append_parent(ref)
            if not parents:
                tqdm.write(f"[{term.curie}] could not find parent")
                term.append_parent(ROOT)

            diseases = graph.query(
                f"SELECT ?p WHERE {{ <{uri}> pav:hasVersion/wp:diseaseOntologyTag ?p }}"
            )
            for (disease,) in diseases:  # type:ignore[misc]
                if disease.startswith(DOID_PREFIX):
                    term.annotate_object(
                        contributes_to_condition,
                        Reference(prefix="doid", identifier=disease.removeprefix(DOID_PREFIX)),
                    )

            cells = graph.query(
                f"SELECT ?p WHERE {{ <{uri}> pav:hasVersion/wp:cellTypeOntologyTag ?p }}"
            )
            for (cell,) in cells:  # type:ignore[misc]
                if cell.startswith(CL_PREFIX):
                    term.annotate_object(
                        located_in,
                        Reference(prefix="cl", identifier=cell.removeprefix(CL_PREFIX)),
                    )

            yield term

    from ..api import get_ancestors
    from ..getters import get_ontology

    for pw_reference in list(pw_references):
        pw_references.update(get_ancestors(pw_reference) or set())

    for pw_term in get_ontology("pw"):
        if pw_term.reference in pw_references:
            yield Term(
                reference=pw_term.reference,
                definition=pw_term.definition,
                # PW has issues in hierarchy - there are lots of leaves with no root
                parents=pw_term.parents or [ROOT],
            )


if __name__ == "__main__":
    WikiPathwaysGetter.cli()
