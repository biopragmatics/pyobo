"""Converter for HGNC."""

import itertools as itt
import json
import logging
import typing
from collections import Counter, defaultdict
from collections.abc import Iterable
from operator import attrgetter
from typing import Optional

from tabulate import tabulate
from tqdm.auto import tqdm

from pyobo.api.utils import get_version
from pyobo.resources.so import get_so_name
from pyobo.struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    from_species,
    gene_product_member_of,
    has_gene_product,
    member_of,
    orthologous,
    transcribes_to,
)
from pyobo.struct.typedef import exact_match
from pyobo.utils.path import ensure_path, prefix_directory_join

__all__ = [
    "HGNCGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "hgnc"
DEFINITIONS_URL_FMT = (
    "https://storage.googleapis.com/public-download-files/hgnc/archive/archive/monthly/json/"
    "hgnc_complete_set_{version}.json"
)

previous_symbol_type = SynonymTypeDef.from_text("previous_symbol")
alias_symbol_type = SynonymTypeDef.from_text("alias_symbol")
previous_name_type = SynonymTypeDef.from_text("previous_name")
alias_name_type = SynonymTypeDef.from_text("alias_name")

#: First column is MIRIAM prefix, second column is HGNC key
gene_xrefs = [
    ("ensembl", "ensembl_gene_id"),
    ("ncbigene", "entrez_id"),
    ("cosmic", "cosmic"),
    ("vega", "vega_id"),
    ("ucsc", "ucsc_id"),
    ("merops.entry", "merops"),
    ("lncipedia", "lncipedia"),
    ("orphanet", "orphanet"),
    ("pseudogene", "pseudogene.org"),
    ("ena", "ena"),
    ("refseq", "refseq_accession"),
    ("iuphar.receptor", "iuphar"),
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

SKIP_KEYS = {
    "date_approved_reserved",
    "_version_",
    "uuid",
    "date_modified",
    "date_name_changed",
    "date_symbol_changed",
    "symbol_report_tag",
    "location_sortable",
    "curator_notes",
    "agr",  # repeat of HGNC ID
    "gencc",  # repeat of HGNC ID
    "bioparadigms_slc",  # repeat of symbol
    "lncrnadb",  # repeat of symbol
    "gtrnadb",  # repeat of symbol
    "horde_id",  # repeat of symbol
    "imgt",  # repeat of symbol
    "cd",  # symbol
    "homeodb",  # TODO add to bioregistry, though this is defunct
    "mamit-trnadb",  # TODO add to bioregistry, though this is defunct
}

#: A mapping from HGNC's locus_type annotations to sequence ontology identifiers
LOCUS_TYPE_TO_SO = {
    # protein-coding gene
    "gene with protein product": "0001217",
    "complex locus constituent": "0000997",  # https://github.com/pyobo/pyobo/issues/118#issuecomment-1564520052
    # non-coding RNA
    "RNA, Y": "0002359",
    "RNA, cluster": "",  # TODO see https://github.com/The-Sequence-Ontology/SO-Ontologies/issues/564
    "RNA, long non-coding": "0002127",  # HGNC links to wrong one
    "RNA, micro": "0001265",
    "RNA, misc": "0001266",
    "RNA, ribosomal": "0001637",
    "RNA, small cytoplasmic": "0001266",
    "RNA, small nuclear": "0001268",
    "RNA, small nucleolar": "0001267",
    "RNA, transfer": "0001272",
    "RNA, vault": "0002358",
    # phenotype
    "phenotype only": "0001500",  # https://github.com/pyobo/pyobo/issues/118#issuecomment-1564574892
    # pseudogene
    "T cell receptor pseudogene": "0002099",
    "immunoglobulin pseudogene": "0002098",
    "immunoglobulin gene": "0002122",  # HGNC links to wrong one
    "pseudogene": "0000336",
    # other
    "T cell receptor gene": "0002133",
    "endogenous retrovirus": "0000100",
    "fragile site": "0002349",
    "readthrough": "0000697",  # maybe not right
    "transposable element": "0000111",  # HGNC links to wrong one
    "virus integration site": "",  # TODO see https://github.com/The-Sequence-Ontology/SO-Ontologies/issues/551
    "region": "0001411",  # a small bucket for things that need a better annotation, even higher than "gene"
    "unknown": "0000704",  # gene
    None: "0000704",  # gene
}

IDSPACES = {
    prefix: f"https://bioregistry.io/{prefix}:"
    for prefix in {
        "rgd",
        "mgi",
        "eccode",
        "rnacentral",
        "pubmed",
        "uniprot",
        "mirbase",
        "snornabase",
        "hgnc",
        "hgnc.genegroup",
        "debio",
        "ensembl",
        "NCBIGene",
        "vega",
        "ucsc",
        "ena",
        "ccds",
        "omim",
        "cosmic",
        "merops",
        "orphanet",
        "pseudogene",
        "lncipedia",
        "refseq",
    }
}
IDSPACES.update(
    NCBITaxon="http://purl.obolibrary.org/obo/NCBITaxon_",
    SO="http://purl.obolibrary.org/obo/SO_",
)


class HGNCGetter(Obo):
    """An ontology representation of HGNC's gene nomenclature."""

    bioversions_key = ontology = PREFIX
    typedefs = [
        from_species,
        has_gene_product,
        gene_product_member_of,
        transcribes_to,
        orthologous,
        member_of,
        exact_match,
    ]
    idspaces = IDSPACES
    synonym_typedefs = [
        previous_name_type,
        previous_symbol_type,
        alias_name_type,
        alias_symbol_type,
    ]
    root_terms = [
        Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id))
        for so_id in sorted(set(LOCUS_TYPE_TO_SO.values()))
        if so_id
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self.data_version)


def get_obo(*, force: bool = False) -> Obo:
    """Get HGNC as OBO."""
    return HGNCGetter(force=force)


def get_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Get HGNC terms."""
    if version is None:
        version = get_version("hgnc")
    unhandled_entry_keys: typing.Counter[str] = Counter()
    unhandle_locus_types: defaultdict[str, dict[str, Term]] = defaultdict(dict)
    path = ensure_path(
        PREFIX,
        url=DEFINITIONS_URL_FMT.format(version=version),
        force=force,
        version=version,
        name="hgnc_complete_set.json",
    )
    with open(path) as file:
        entries = json.load(file)["response"]["docs"]

    yield Term.from_triple("NCBITaxon", "9606", "Homo sapiens")
    yield from sorted(
        {
            Term(reference=Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id)))
            for so_id in sorted(LOCUS_TYPE_TO_SO.values())
            if so_id
        },
        key=attrgetter("identifier"),
    )

    statuses = set()
    for entry in tqdm(entries, desc=f"Mapping {PREFIX}", unit="gene", unit_scale=True):
        name, symbol, identifier = (
            entry.pop("name"),
            entry.pop("symbol"),
            entry.pop("hgnc_id")[len("HGNC:") :],
        )
        status = entry.pop("status")
        if status == "Approved":
            is_obsolete = False
        elif status not in statuses:
            statuses.add(status)
            tqdm.write(f"[{PREFIX}] unhandled {status}")
            is_obsolete = True
        else:
            raise ValueError(f"Unhandled status for hgnc:{identifier}: {status}")

        term = Term(
            definition=name,
            reference=Reference(prefix=PREFIX, identifier=identifier, name=symbol),
            is_obsolete=is_obsolete,
        )

        for uniprot_id in entry.pop("uniprot_ids", []):
            term.append_relationship(
                has_gene_product,
                Reference(prefix="uniprot", identifier=uniprot_id),
            )
        for ec_code in entry.pop("enzyme_id", []):
            if "-" in ec_code:
                continue  # only add concrete annotations
            term.append_relationship(
                gene_product_member_of,
                Reference(prefix="eccode", identifier=ec_code),
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
                    prefix="mirbase",
                    identifier=mirbase_id,
                ),
            )
        snornabase_id = entry.pop("snornabase", None)
        if snornabase_id:
            term.append_relationship(
                transcribes_to, Reference(prefix="snornabase", identifier=snornabase_id)
            )

        for rgd_curie in entry.pop("rgd_id", []):
            if not rgd_curie.startswith("RGD:"):
                tqdm.write(f"hgnc:{identifier} had bad RGD CURIE: {rgd_curie}")
                continue
            rgd_id = rgd_curie[len("RGD:") :]
            term.append_relationship(
                orthologous,
                Reference(prefix="rgd", identifier=rgd_id),
            )
        for mgi_curie in entry.pop("mgd_id", []):
            if not mgi_curie.startswith("MGI:"):
                tqdm.write(f"hgnc:{identifier} had bad MGI CURIE: {mgi_curie}")
                continue
            mgi_id = mgi_curie[len("MGI:") :]
            if not mgi_id:
                continue
            term.append_relationship(
                orthologous,
                Reference(prefix="mgi", identifier=mgi_id),
            )

        iuphar = entry.pop("iuphar", None)
        if iuphar:
            if iuphar.startswith("objectId:"):
                term.append_exact_match(
                    Reference(prefix="iuphar.receptor", identifier=iuphar[len("objectId:") :])
                )
            elif iuphar.startswith("ligandId:"):
                term.append_exact_match(
                    Reference(prefix="iuphar.ligand", identifier=iuphar[len("ligandId:") :])
                )
            else:
                tqdm.write(f"unhandled IUPHAR: {iuphar}")

        for lrg_info in entry.pop("lsdb", []):
            if lrg_info.startswith("LRG_"):
                lrg_curie = lrg_info.split("|")[0]
                _, lrg_id = lrg_curie.split("_")
                term.append_xref(Reference(prefix="lrg", identifier=lrg_id))

        for xref_prefix, key in gene_xrefs:
            xref_identifiers = entry.pop(key, None)
            if xref_identifiers is None:
                continue
            if isinstance(xref_identifiers, (str, int)):
                xref_identifiers = [str(xref_identifiers)]

            if xref_prefix == "merops.entry":
                continue
                # e.g., XM02-001 should be rewritten as XM02.001
                xref_identifiers = [i.replace("-", ".") for i in xref_identifiers]

            if xref_prefix == "refseq":
                # e.g., strip off dots without substantiated record versions like in NM_021728.
                xref_identifiers = [i.strip(".") for i in xref_identifiers]

            if len(xref_identifiers) == 1:
                term.append_exact_match(
                    Reference(prefix=xref_prefix, identifier=str(xref_identifiers[0]))
                )
            else:
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
        for previous_symbol in itt.chain(
            entry.pop("previous_symbol", []), entry.pop("prev_symbol", [])
        ):
            term.append_synonym(Synonym(name=previous_symbol, type=previous_symbol_type))
        for previous_name in entry.pop("prev_name", []):
            term.append_synonym(Synonym(name=previous_name, type=previous_name_type))

        for prop in ["location"]:
            value = entry.pop(prop, None)
            if value:
                term.append_property(prop, value)

        locus_type = entry.pop("locus_type")
        locus_group = entry.pop("locus_group")
        so_id = LOCUS_TYPE_TO_SO.get(locus_type)
        if so_id:
            term.append_parent(Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id)))
        else:
            term.append_parent(
                Reference(prefix="SO", identifier="0000704", name=get_so_name("0000704"))
            )  # gene
            unhandle_locus_types[locus_type][identifier] = term
            term.append_property("locus_type", locus_type)
            term.append_property("locus_group", locus_group)

        term.set_species(identifier="9606", name="Homo sapiens")

        for key in entry:
            if key not in SKIP_KEYS:
                unhandled_entry_keys[key] += 1
        yield term

    with open(prefix_directory_join(PREFIX, name="unhandled.json"), "w") as file:
        json.dump(
            {
                k: {hgnc_id: term.name for hgnc_id, term in v.items()}
                for k, v in unhandle_locus_types.items()
            },
            file,
            indent=2,
        )

    with open(prefix_directory_join(PREFIX, name="unhandled.md"), "w") as file:
        for k, v in sorted(unhandle_locus_types.items()):
            t = tabulate(
                [
                    (
                        hgnc_id,
                        term.name,
                        term.is_obsolete,
                        term.bioregistry_link,
                        ", ".join(
                            p.bioregistry_link for p in term.provenance if p.bioregistry_link
                        ),
                    )
                    for hgnc_id, term in sorted(v.items())
                ],
                headers=["hgnc_id", "name", "obsolete", "link", "provenance"],
                tablefmt="github",
            )
            print(f"## {k} ({len(v)})", file=file)
            print(t, "\n", file=file)

    unhandle_locus_type_counter = Counter(
        {locus_type: len(d) for locus_type, d in unhandle_locus_types.items()}
    )
    logger.warning(
        "Unhandled locus types:\n%s", tabulate(unhandle_locus_type_counter.most_common())
    )
    logger.warning("Unhandled keys:\n%s", tabulate(unhandled_entry_keys.most_common()))


if __name__ == "__main__":
    HGNCGetter.cli()
