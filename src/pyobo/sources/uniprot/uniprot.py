"""Converter for UniProt."""

from collections.abc import Iterable
from operator import attrgetter
from pathlib import Path
from typing import Optional, cast

from tqdm.auto import tqdm

from pyobo import Obo, Reference
from pyobo.api.utils import get_version
from pyobo.constants import RAW_MODULE
from pyobo.identifier_utils import standardize_ec
from pyobo.struct import Term, derives_from, enables, from_species, participates_in
from pyobo.struct.typedef import gene_product_of, located_in, molecularly_interacts_with
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
    "lit_pubmed_id",
    "xref_pdb",
    "xref_proteomes",
    "xref_geneid",
    "rhea",
    "go_c",
    "go_f",
    "go_p",
    "ft_binding",
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
    typedefs = [
        from_species,
        enables,
        participates_in,
        gene_product_of,
        molecularly_interacts_with,
        derives_from,
        located_in,
    ]

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
        for (
            uniprot_id,
            accession,
            taxonomy_id,
            _name,  # this field should have the name, but it's a mismatch of random name annotations
            ecs,
            pubmeds,
            pdbs,
            proteome,
            gene_ids,
            rhea_curies,
            go_components,
            go_functions,
            go_processes,
            bindings,
            description,
        ) in tqdm(reader, desc="Mapping UniProt", unit_scale=True):
            if description:
                description = description.removeprefix("FUNCTION: ")
            term = Term(
                reference=Reference(prefix=PREFIX, identifier=uniprot_id, name=accession),
                # definition=description or None,
            )
            term.set_species(taxonomy_id)
            if gene_ids:
                for gene_id in gene_ids.split(";"):
                    term.append_relationship(
                        gene_product_of, Reference(prefix="ncbigene", identifier=gene_id.strip())
                    )

            # TODO add type=Reference(prefix="xsd", identifier="boolean")
            term.append_property("reviewed", "true")

            for go_process_ref in _parse_go(go_processes):
                term.append_relationship(participates_in, go_process_ref)
            for go_function_ref in _parse_go(go_functions):
                term.append_relationship(enables, go_function_ref)
            for go_component_ref in _parse_go(go_components):
                term.append_relationship(located_in, go_component_ref)

            if proteome:
                uniprot_proteome_id = proteome.split(":")[0]
                term.append_relationship(
                    derives_from,
                    Reference(prefix="uniprot.proteome", identifier=uniprot_proteome_id),
                )

            if rhea_curies:
                for rhea_curie in rhea_curies.split(" "):
                    term.append_relationship(
                        # FIXME this needs a different relation than enables
                        #  see https://github.com/biopragmatics/pyobo/pull/168#issuecomment-1918680152
                        enables,
                        cast(Reference, Reference.from_curie(rhea_curie, strict=True)),
                    )

            if bindings:
                binding_references = set()
                for part in bindings.split(";"):
                    part = part.strip()
                    if part.startswith("/ligand_id"):
                        curie = part.removeprefix('/ligand_id="').rstrip('"')
                        binding_references.add(
                            cast(Reference, Reference.from_curie(curie, strict=True))
                        )
                for binding_reference in sorted(binding_references, key=attrgetter("curie")):
                    term.append_relationship(molecularly_interacts_with, binding_reference)

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


def _parse_go(go_terms) -> list[Reference]:
    rv = []
    if go_terms:
        for go_term in go_terms.split(";"):
            go_id = go_term.rsplit("[GO:")[1].rstrip("]")
            rv.append(Reference(prefix="go", identifier=go_id))
    return rv


def ensure(version: Optional[str] = None, force: bool = False) -> Path:
    """Ensure the reviewed uniprot names are available."""
    if version is None:
        version = get_version("uniprot")
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
