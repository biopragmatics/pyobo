# -*- coding: utf-8 -*-

"""Converter for HGNC."""

import json
import logging
from collections import Counter
from typing import Iterable

from tabulate import tabulate
from tqdm import tqdm

from ..api import get_name
from ..struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    from_species,
    gene_product_is_a,
    has_gene_product,
    member_of,
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
    # ("mgi", "mgd_id"),
    ("ccds", "ccds_id"),
    # ("rgd", "rgd_id"),
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

# TODO
SO = {
    # protein-coding gene
    "gene with protein product": "0001217",
    # non-coding RNA
    "RNA, Y": "",  # TODO
    "RNA, cluster": "",  # TODO
    "RNA, long non-coding": "0002127",
    "RNA, micro": "0001265",
    "RNA, misc": "0001266",
    "RNA, ribosomal": "0001637",
    "RNA, small cytoplasmic": "",
    "RNA, small nuclear": "0001268",
    "RNA, small nucleolar": "0001267",
    "RNA, transfer": "0001272",
    "RNA, vault": "",  # see RNA analog SO:0000404
    # phenotype
    "phenotype only": "",  # TODO
    # pseudogene
    "T cell receptor pseudogene": "0002099",
    "immunoglobulin pseudogene": "0002098",
    "immunoglobulin gene": "0002122",
    "pseudogene": "0000336",
    # other
    "T cell receptor gene": "0002133",
    "complex locus constituent": "",
    "endogenous retrovirus": "0000100",
    "fragile site": "",  # TODO
    "protocadherin": "",  # TODO
    "readthrough": "0000697",  # maybe not right
    "region": "",
    "transposable element": "0000111",
    "virus integration site": "",  # TODO
}


def get_obo(force: bool = False) -> Obo:
    """Get HGNC as OBO."""
    return Obo(
        ontology=PREFIX,
        name="HGNC",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force),
        typedefs=[
            from_species,
            has_gene_product,
            gene_product_is_a,
            transcribes_to,
            orthologous,
            member_of,
        ],
        synonym_typedefs=[
            previous_name_type,
            previous_symbol_type,
            alias_name_type,
            alias_symbol_type,
        ],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_terms(force: bool = False) -> Iterable[Term]:  # noqa:C901
    """Get HGNC terms."""
    unhandled_entry_keys = Counter()
    unhandle_locus_types = Counter()
    path = ensure_path(PREFIX, url=DEFINITIONS_URL, force=force)
    with open(path) as file:
        entries = json.load(file)["response"]["docs"]

    for so_id in sorted(SO.values()):
        if so_id:
            yield Term(reference=Reference.auto("SO", so_id))
    for entry in tqdm(entries, desc=f"Mapping {PREFIX}"):
        name, symbol, identifier = (
            entry.pop("name"),
            entry.pop("symbol"),
            entry.pop("hgnc_id")[len("HGNC:") :],
        )

        term = Term(
            definition=name,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=symbol),
        )

        for uniprot_id in entry.pop("uniprot_ids", []):
            term.append_relationship(
                has_gene_product,
                Reference(
                    prefix="uniprot",
                    identifier=uniprot_id,
                    name=get_name(
                        "uniprot",
                        uniprot_id,
                    ),
                ),
            )
        for ec_code in entry.pop("enzyme_id", []):
            term.append_relationship(
                gene_product_is_a,
                Reference(prefix="ec-code", identifier=ec_code, name=get_name("ec-code", ec_code)),
            )
        for rna_central_ids in entry.pop("rna_central_id", []):
            for rna_central_id in rna_central_ids.split(","):
                term.append_relationship(
                    transcribes_to,
                    Reference(prefix="rnacentral", identifier=rna_central_id.strip()),
                )
        mirbase_id = entry.pop("mirbase", None)
        if mirbase_id:
            term.append_relationship(
                transcribes_to,
                Reference(
                    prefix="mirbase", identifier=mirbase_id, name=get_name("mirbase", mirbase_id)
                ),
            )
        snornabase_id = entry.pop("snornabase", None)
        if snornabase_id:
            term.append_relationship(
                transcribes_to, Reference(prefix="snornabase", identifier=snornabase_id)
            )

        for rgd_curie in entry.pop("rgd_id", []):
            rgd_id = rgd_curie[len("RGD:") :]
            term.append_relationship(
                orthologous,
                Reference(prefix="rgd", identifier=rgd_id, name=get_name("rgd", rgd_id)),
            )
        for mgi_curie in entry.pop("mgd_id", []):
            mgi_id = mgi_curie[len("MGI:") :]
            term.append_relationship(
                orthologous,
                Reference(prefix="mgi", identifier=mgi_id, name=get_name("mgi", mgi_id)),
            )

        for xref_prefix, key in gene_xrefs:
            xref_identifiers = entry.pop(key, None)
            if xref_identifiers is None:
                continue
            if not isinstance(xref_identifiers, list):
                xref_identifiers = [xref_identifiers]
            for xref_identifier in xref_identifiers:
                term.append_xref(Reference(prefix=xref_prefix, identifier=str(xref_identifier)))

        for pubmed_id in entry.pop("pubmed_id", []):
            term.append_provenance(Reference(prefix="pubmed", identifier=str(pubmed_id)))

        gene_group_ids = entry.pop("gene_group_id", [])
        gene_groups = entry.pop("gene_group", [])
        for gene_group_id, gene_group_label in zip(gene_group_ids, gene_groups):
            term.append_relationship(
                member_of,
                Reference(
                    prefix="hgnc.genegroup",
                    identifier=str(gene_group_id),
                    name=gene_group_label,
                ),
            )

        for alias_symbol in entry.pop("alias_symbol", []):
            term.append_synonym(Synonym(name=alias_symbol, type=alias_symbol_type))
        for alias_name in entry.pop("alias_name", []):
            term.append_synonym(Synonym(name=alias_name, type=alias_name_type))
        for previous_symbol in entry.pop("previous_symbol", []):
            term.append_synonym(Synonym(name=previous_symbol, type=previous_symbol_type))
        for previous_name in entry.pop("prev_name", []):
            term.append_synonym(Synonym(name=previous_name, type=previous_name_type))

        for prop in ["locus_group", "location"]:
            value = entry.pop(prop, None)
            if value:
                term.append_property(prop, value)

        locus_type = entry.pop("locus_type")
        so_id = SO.get(locus_type)
        if locus_type == "unknown":
            pass
        elif so_id:
            term.append_parent(Reference.auto("SO", so_id))
        else:
            unhandle_locus_types[locus_type] += 1
            term.append_property("locus_type", locus_type)

        term.set_species(identifier="9606", name="Homo sapiens")

        for key in entry:
            unhandled_entry_keys[key] += 1
        yield term

    logger.warning("Unhandled locus types:\n%s", tabulate(unhandle_locus_types.most_common()))
    logger.warning("Unhandled keys:\n%s", tabulate(unhandled_entry_keys.most_common()))


if __name__ == "__main__":
    get_obo(force=True).write_default(write_obo=True, write_obograph=True, force=True)
