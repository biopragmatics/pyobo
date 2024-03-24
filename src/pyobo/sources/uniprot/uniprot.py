# -*- coding: utf-8 -*-

"""Converter for UniProt."""

from pathlib import Path
from typing import Iterable, Optional

import bioversions
from tqdm.auto import tqdm

from pyobo import Obo, Reference
from pyobo.constants import RAW_MODULE
from pyobo.identifier_utils import standardize_ec
from pyobo.struct import Term, derives_from, enables, from_species, participates_in
from pyobo.utils.io import open_reader

PREFIX = "uniprot"
BASE_URL = "https://rest.uniprot.org/uniprotkb/stream"
SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
QUERY = "(*) AND (reviewed:true)"
FIELDS = [
    "accession",
    "id",
    "organism_id",
    "protein_name",
    "ec",
    "ft_binding",
    "go",
    "xref_proteomes",
    "rhea",
    "lit_pubmed_id",
    "xref_pdb",
    "cc_function",
]
PARAMS = {
    "compressed": "true",
    "format": "tsv",
    # "size": 10,  # only used with search
    "query": QUERY,
    "fields": FIELDS,
}


class UniProtGetter(Obo):
    """An ontology representation of the UniProt database."""

    bioversions_key = ontology = PREFIX
    typedefs = [from_species, enables, participates_in]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield from iter_terms(version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get UniProt as OBO."""
    return UniProtGetter(force=force)


def iter_terms(version: Optional[str] = None) -> Iterable[Term]:
    """Iterate over UniProt Terms."""
    with open_reader(ensure(version=version)) as reader:
        _ = next(reader)  # header
        for uniprot_id, name, taxonomy_id, _synonyms, ecs, pubmeds, pdbs in tqdm(
            reader, desc="Mapping UniProt", unit_scale=True
        ):
            term = Term.from_triple(prefix=PREFIX, identifier=uniprot_id, name=name)
            # TODO add gene encodes from relationship
            # TODO add description
            term.set_species(taxonomy_id)
            term.append_property(
                "reviewed", "true"
            )  # type=Reference(prefix="xsd", identifier="boolean")

            binding_site = None
            go_terms = ""
            if go_terms:
                for go_term in go_terms.split(";"):
                    go_id = go_term.rsplit("[GO:")[1].rstrip("]")
                    term.append_relationship(
                        # This relationship isn't correct in general, e.g.,
                        # a protein doesn't participate in a molecular function
                        participates_in,
                        Reference(prefix="go", identifier=go_id),
                    )

            proteomes = ""
            if proteomes:
                # TODO need example with multiple
                for proteome in proteomes.split(";"):
                    uniprot_proteome_id = proteome.split(":")[0]
                    term.append_relationship(
                        derives_from,
                        Reference(prefix="uniprot.proteome", identifier=uniprot_proteome_id),
                    )

            rhea_curies = ""
            if rhea_curies:
                for rhea_curie in rhea_curies.split(" "):
                    term.append_relationship(
                        # FIXME this needs a different relation,
                        #  see https://github.com/biopragmatics/pyobo/pull/168#issuecomment-1918680152
                        participates_in,
                        Reference.from_curie(rhea_curie),
                    )

            binding_sites = ""
            # Example: BINDING 305; /ligand="Zn(2+)"; /ligand_id="ChEBI:CHEBI:29105"; /ligand_note="catalytic"; /evidence="ECO:0000255|PROSITE-ProRule:PRU10095"; BINDING 309; /ligand="Zn(2+)"; /ligand_id="ChEBI:CHEBI:29105"; /ligand_note="catalytic"; /evidence="ECO:0000255|PROSITE-ProRule:PRU10095"; BINDING 385; /ligand="Zn(2+)"; /ligand_id="ChEBI:CHEBI:29105"; /ligand_note="catalytic"; /evidence="ECO:0000255|PROSITE-ProRule:PRU10095"

            if ecs:
                for ec in ecs.split(";"):
                    term.append_relationship(
                        enables, Reference(prefix="eccode", identifier=standardize_ec(ec))
                    )
            for pubmed in pubmeds.split(";"):
                if pubmed:
                    term.append_provenance(Reference(prefix="pubmed", identifier=pubmed.strip()))
            for pdb in pdbs.split(";"):
                if pdb:
                    term.append_xref(Reference(prefix="pdb", identifier=pdb.strip()))
            yield term


def ensure(version: Optional[str] = None, force: bool = False) -> Path:
    """Ensure the reviewed uniprot names are available."""
    if version is None:
        version = bioversions.get_version("uniprot")
    return RAW_MODULE.ensure(
        PREFIX,
        version,
        force=force,
        name="reviewed.tsv.gz",
        url=BASE_URL,  # switch to SEARCH_URL for debugging
        download_kwargs={"backend": "requests", "params": PARAMS},
    )


if __name__ == "__main__":
    UniProtGetter.cli()
