# -*- coding: utf-8 -*-

"""Converter for HGNC."""

import json
import logging
from typing import Iterable

from tqdm import tqdm

from ..struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    from_species,
    gene_product_is_a,
    has_gene_product,
    orthologous,
    transcribes_to,
)
from ..utils.path import ensure_path

logger = logging.getLogger(__name__)

PREFIX = "hgnc"
DEFINITIONS_URL = "ftp://ftp.ebi.ac.uk/pub/databases/genenames/new/json/hgnc_complete_set.json"

previous_symbol_type = SynonymTypeDef(id="previous_symbol", name="previous symbol")
alias_symbol_type = SynonymTypeDef(id="alias_symbol", name="alias symbol")
previous_name_type = SynonymTypeDef(id="previous_name", name="previous name")
alias_name_type = SynonymTypeDef(id="alias_name", name="alias name")

#: First column is MIRIAM prefix, second column is HGNC key
gene_xrefs = [
    ("ensembl", "ensembl_gene_id"),
    ("ncbigene", "entrez_id"),
    ("cosmic", "cosmic"),
    ("vega", "vega_id"),
    ("ucsc", "ucsc_id"),
    ("merops", "merops"),
    ("lncipedia", "lncipedia"),
    ("orphanet", "orphanet"),
    ("pseudogene", "pseudogene.org"),
    ("ena", "ena"),
    ("refseq", "refseq_accession"),
    ("mgi", "mgd_id"),
    ("ccds", "ccds_id"),
    ("rgd", "rgd_id"),
    ("omim", "omim_id"),
    # ('uniprot', 'uniprot_ids'),
    # ('ec-code', 'enzyme_id'),
    # ('rnacentral', 'rna_central_id'),
    # ('mirbase', 'mirbase'),
    # ('snornabase', 'snornabase'),
]

#: Encodings from https://www.genenames.org/cgi-bin/statistics
#: To see all, do: ``cat hgnc_complete_set.json | jq .response.docs[].locus_type | sort | uniq``
ENCODINGS = {
    # protein-coding gene
    "gene with protein product": "GRP",
    # non-coding RNA
    "RNA, Y": "GR",
    "RNA, cluster": "GR",
    "RNA, long non-coding": "GR",
    "RNA, micro": "GM",
    "RNA, misc": "GR",
    "RNA, ribosomal": "GR",
    "RNA, small cytoplasmic": "GR",
    "RNA, small nuclear": "GR",
    "RNA, small nucleolar": "GR",
    "RNA, transfer": "GR",
    "RNA, vault": "GR",
    # phenotype
    "phenotype only": "G",
    # pseudogene
    "T cell receptor pseudogene": "GRP",
    "immunoglobulin pseudogene": "GRP",
    "immunoglobulin gene": "GRP",
    "pseudogene": "G",
    # other
    "T cell receptor gene": "GRP",
    "complex locus constituent": "G",
    "endogenous retrovirus": "G",
    "fragile site": "G",
    "protocadherin": "GRP",
    "readthrough": "G",
    "region": "G",
    "transposable element": "G",
    "virus integration site": "G",
    "unknown": "GRP",
}


def get_obo() -> Obo:
    """Get HGNC as OBO."""
    return Obo(
        ontology=PREFIX,
        name="HGNC",
        iter_terms=get_terms,
        typedefs=[from_species, has_gene_product, gene_product_is_a, transcribes_to, orthologous],
        synonym_typedefs=[
            previous_name_type,
            previous_symbol_type,
            alias_name_type,
            alias_symbol_type,
        ],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_terms() -> Iterable[Term]:
    """Get HGNC terms."""
    unhandled = set()
    path = ensure_path(PREFIX, url=DEFINITIONS_URL)
    with open(path) as file:
        entries = json.load(file)["response"]["docs"]

    for entry in tqdm(entries, desc=f"Mapping {PREFIX}"):
        name, symbol, identifier = (
            entry.pop("name"),
            entry.pop("symbol"),
            entry.pop("hgnc_id")[len("HGNC:") :],
        )

        relations = []
        for uniprot_id in entry.pop("uniprot_ids", []):
            relations.append((has_gene_product, Reference(prefix="uniprot", identifier=uniprot_id)))
        for ec_code in entry.pop("enzyme_id", []):
            relations.append((gene_product_is_a, Reference(prefix="ec-code", identifier=ec_code)))
        for rna_central_id in entry.pop("rna_central_id", []):
            relations.append(
                (transcribes_to, Reference(prefix="rnacentral", identifier=rna_central_id))
            )
        mirbase_id = entry.pop("mirbase", None)
        if mirbase_id:
            relations.append((transcribes_to, Reference(prefix="mirbase", identifier=mirbase_id)))
        snornabase_id = entry.pop("snornabase", None)
        if snornabase_id:
            relations.append(
                (transcribes_to, Reference(prefix="snornabase", identifier=snornabase_id))
            )

        for rgd_id in entry.pop("rgd_id", []):
            relations.append(
                (orthologous, Reference(prefix="rgd", identifier=rgd_id[len("RGD:") :]))
            )
        for mgi_id in entry.pop("mgd_id", []):
            relations.append(
                (orthologous, Reference(prefix="mgi", identifier=mgi_id[len("MGI:") :]))
            )

        xrefs = []
        for xref_prefix, key in gene_xrefs:
            xref_identifiers = entry.pop(key, None)
            if xref_identifiers is None:
                continue
            if not isinstance(xref_identifiers, list):
                xref_identifiers = [xref_identifiers]
            for xref_identifier in xref_identifiers:
                xrefs.append(Reference(prefix=xref_prefix, identifier=str(xref_identifier)))

        provenance = [
            Reference(prefix="pubmed", identifier=str(pubmed_id))
            for pubmed_id in entry.pop("pubmed_id", [])
        ]

        gene_group_ids = entry.pop("gene_group_id", [])
        gene_groups = entry.pop("gene_group", [])
        parents = [
            Reference(
                prefix="hgnc.genefamily",
                identifier=str(hgncgenefamily_id),
                name=gene_group_label,
            )
            for hgncgenefamily_id, gene_group_label in zip(gene_group_ids, gene_groups)
        ]

        synonyms = []
        for alias_symbol in entry.pop("alias_symbol", []):
            synonyms.append(Synonym(name=alias_symbol, type=alias_symbol_type))
        for alias_name in entry.pop("alias_name", []):
            synonyms.append(Synonym(name=alias_name, type=alias_name_type))
        for previous_symbol in entry.pop("previous_symbol", []):
            synonyms.append(Synonym(name=previous_symbol, type=previous_symbol_type))
        for previous_name in entry.pop("prev_name", []):
            synonyms.append(Synonym(name=previous_name, type=previous_name_type))

        term = Term(
            definition=name,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=symbol),
            xrefs=xrefs,
            provenance=provenance,
            parents=parents,
            synonyms=synonyms,
        )

        for typedef, reference in relations:
            term.append_relationship(typedef, reference)

        for prop in ["locus_group", "locus_type", "location"]:
            value = entry.get(prop)
            if value:
                term.append_property(prop, value)
        term.set_species(identifier="9606", name="Homo sapiens")

        unhandled.update(set(entry))
        yield term

    # logger.warning('Unhandled:')
    # for u in sorted(unhandled):
    #     logger.warning(u)


if __name__ == "__main__":
    get_obo().write_default()
