"""Converter for HGNC."""

import itertools as itt
import json
import logging
import typing
from collections import Counter, defaultdict
from collections.abc import Iterable

import obographs
import pydantic
from tabulate import tabulate
from tqdm.auto import tqdm

from pyobo.api.utils import get_version
from pyobo.resources.so import get_so_name
from pyobo.struct import (
    Annotation,
    Obo,
    OBOLiteral,
    Reference,
    Term,
    from_species,
    gene_product_member_of,
    has_gene_product,
    is_mentioned_by,
    member_of,
    orthologous,
    transcribes_to,
)
from pyobo.struct.struct import gene_symbol_synonym, previous_gene_symbol, previous_name
from pyobo.struct.typedef import comment, ends, exact_match, located_in, starts
from pyobo.utils.path import ensure_path

__all__ = [
    "HGNCGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "hgnc"
DEFINITIONS_URL_FMT = (
    "https://storage.googleapis.com/public-download-files/hgnc/archive/archive/monthly/json/"
    "hgnc_complete_set_{version}.json"
)

CHR_URL = (
    "https://raw.githubusercontent.com/monarch-initiative/monochrom/refs/heads/master/chr.json"
)

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
    "mane_select",  # TODO
}

#: A mapping from HGNC's locus_type annotations to sequence ontology identifiers
LOCUS_TYPE_TO_SO = {
    # protein-coding gene
    "gene with protein product": "0001217",
    "complex locus constituent": "0000997",  # https://github.com/pyobo/pyobo/issues/118#issuecomment-1564520052
    # non-coding RNA
    "RNA, Y": "0002359",
    "RNA, cluster": "0003001",  # TODO see https://github.com/The-Sequence-Ontology/SO-Ontologies/issues/564
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
    "virus integration site": "0003002",  # TODO see https://github.com/The-Sequence-Ontology/SO-Ontologies/issues/551
    "region": "0001411",  # a small bucket for things that need a better annotation, even higher than "gene"
    "unknown": "0000704",  # gene
    None: "0000704",  # gene
}

PUBLICATION_TERM = Term(
    reference=Reference(prefix="IAO", identifier="0000013", name="journal article")
)

#: Indicates the cytogenetic location of the gene or region on the chromsome.
#: In the absence of that information one of the following may be listed.
QUALIFIERS = {
    " not on reference assembly": "not on reference assembly -named gene is not annotated on the current version of the Genome Reference Consortium human reference assembly; may have been annotated on previous assembly versions or on a non-reference human assembly",
    " unplaced": "unplaced - named gene is annotated on an unplaced/unlocalized scaffold of the human reference assembly",
    " alternate reference locus": "reserved - named gene has never been annotated on any human assembly",
}


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
        is_mentioned_by,
        located_in,
        starts,
        ends,
        comment,
    ]
    synonym_typedefs = [
        previous_name,
        previous_gene_symbol,
        gene_symbol_synonym,
    ]
    root_terms = [
        Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id))
        for so_id in sorted(set(LOCUS_TYPE_TO_SO.values()))
        if so_id
    ]
    skip_maintainers = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self.data_version)


def _get_location_to_chr() -> dict[str, Reference]:
    uri_prefix = "http://purl.obolibrary.org/obo/CHR_9606-chr"
    graph: obographs.Graph = obographs.read(CHR_URL, squeeze=True)
    rv = {}
    for node in graph.nodes:
        if node.id.startswith(uri_prefix):
            identifier = node.id.removeprefix(uri_prefix)
            rv[identifier] = Reference(
                prefix="CHR", identifier=f"9606-chr{identifier}", name=node.lbl
            )
    return rv


def get_terms(version: str | None = None, force: bool = False) -> Iterable[Term]:
    """Get HGNC terms."""
    if version is None:
        version = get_version("hgnc")

    unhandled_locations: defaultdict[str, set[str]] = defaultdict(set)
    location_to_chr = _get_location_to_chr()

    unhandled_entry_keys: typing.Counter[str] = Counter()
    path = ensure_path(
        PREFIX,
        url=DEFINITIONS_URL_FMT.format(version=version),
        force=force,
        version=version,
        name="hgnc_complete_set.json",
    )
    with path.open() as file:
        entries = json.load(file)["response"]["docs"]

    yield Term.from_triple("NCBITaxon", "9606", "Homo sapiens")
    _so_ids: set[str] = {s for s in LOCUS_TYPE_TO_SO.values() if s}
    yield from [
        Term(reference=Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id)))
        for so_id in sorted(_so_ids)
    ]

    statuses = set()
    for entry in tqdm(entries, desc=f"Mapping {PREFIX}", unit="gene", unit_scale=True):
        name, symbol, identifier = (
            entry.pop("name"),
            entry.pop("symbol"),
            entry.pop("hgnc_id")[len("HGNC:") :],
        )
        status = entry.pop("status")
        if status == "Approved":
            is_obsolete = None
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
                Reference(prefix="ec", identifier=ec_code.strip()),
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
                tqdm.write(f"[hgnc:{identifier}] had bad MGI CURIE: {mgi_curie}")
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
            elif iuphar.startswith("HGNC:"):
                pass
            else:
                tqdm.write(f"[hgnc:{identifier}] unhandled IUPHAR: {iuphar}")

        for lrg_info in entry.pop("lsdb", []):
            if lrg_info.startswith("LRG_"):
                lrg_curie = lrg_info.split("|")[0]
                _, lrg_id = lrg_curie.split("_")
                term.append_xref(Reference(prefix="lrg", identifier=lrg_id))

        for xref_prefix, key in gene_xrefs:
            xref_identifiers = entry.pop(key, None)
            if xref_identifiers is None:
                continue
            if isinstance(xref_identifiers, str | int):
                xref_identifiers = [str(xref_identifiers)]

            if xref_prefix == "merops.entry":
                # e.g., XM02-001 should be rewritten as XM02.001
                xref_identifiers = [i.replace("-", ".") for i in xref_identifiers]

            if xref_prefix == "refseq":
                # e.g., strip off dots without substantiated record versions like in NM_021728.
                xref_identifiers = [i.strip(".") for i in xref_identifiers]

            if len(xref_identifiers) == 1:
                try:
                    xref = Reference(prefix=xref_prefix, identifier=str(xref_identifiers[0]))
                except pydantic.ValidationError:
                    tqdm.write(
                        f"[hgnc:{identifier}] had bad {key} xref: {xref_prefix}:{xref_identifiers[0]}"
                    )
                    continue
                else:
                    term.append_exact_match(xref)
            else:
                for xref_identifier in xref_identifiers:
                    term.append_xref(Reference(prefix=xref_prefix, identifier=str(xref_identifier)))

        for pubmed_id in entry.pop("pubmed_id", []):
            term.append_mentioned_by(Reference(prefix="pubmed", identifier=str(pubmed_id)))

        gene_group_ids = entry.pop("gene_group_id", [])
        gene_groups = entry.pop("gene_group", [])
        for gene_group_id, gene_group_label in zip(gene_group_ids, gene_groups, strict=False):
            term.append_relationship(
                member_of,
                Reference(
                    prefix="hgnc.genegroup",
                    identifier=str(gene_group_id),
                    name=gene_group_label,
                ),
            )

        for alias_symbol in entry.pop("alias_symbol", []):
            term.append_synonym(alias_symbol, type=gene_symbol_synonym)
        for alias_name in entry.pop("alias_name", []):
            # regular synonym, no type needed.
            term.append_synonym(alias_name)
        for previous_symbol in itt.chain(
            entry.pop("previous_symbol", []), entry.pop("prev_symbol", [])
        ):
            term.append_synonym(previous_symbol, type=previous_gene_symbol)
        for previous_name_ in entry.pop("prev_name", []):
            term.append_synonym(previous_name_, type=previous_name)

        location: str | None = entry.pop("location", None)
        if location is not None and location not in {
            "not on reference assembly",
            "unplaced",
            "reserved",
        }:
            annotations = []
            for qualifier_suffix, qualifier_text in QUALIFIERS.items():
                if location.endswith(qualifier_suffix):
                    location = location.removesuffix(qualifier_suffix)
                    annotations.append(
                        Annotation(
                            predicate=comment.reference, value=OBOLiteral.string(qualifier_text)
                        )
                    )
                    break

            if location in location_to_chr:
                term.append_relationship(
                    located_in, location_to_chr[location], annotations=annotations
                )
            elif location == "mitochondria":
                term.append_relationship(
                    located_in,
                    Reference(prefix="go", identifier="0000262", name="mitochondrial chromosome"),
                    annotations=annotations,
                )
            elif " and " in location:
                left, _, right = location.partition(" and ")
                if left not in location_to_chr:
                    unhandled_locations[left].add(identifier)
                elif right not in location_to_chr:
                    unhandled_locations[right].add(identifier)
                elif left in location_to_chr and right in location_to_chr:
                    term.append_relationship(
                        located_in, location_to_chr[left], annotations=annotations
                    )
                    term.append_relationship(
                        located_in, location_to_chr[right], annotations=annotations
                    )
                else:
                    unhandled_locations[location].add(identifier)
            elif " or " in location:
                left, _, right = location.partition(" or ")
                if left not in location_to_chr:
                    unhandled_locations[left].add(identifier)
                elif right not in location_to_chr:
                    unhandled_locations[right].add(identifier)
                elif left in location_to_chr and right in location_to_chr:
                    # FIXME implement
                    unhandled_locations[location].add(identifier)
                else:
                    unhandled_locations[location].add(identifier)
            elif "-" in location:
                start, _, end = location.partition("-")

                # the range that sarts with a q needs
                # the chromosome moved over, like in
                # 17q24.2-q24.3
                if end.startswith("q"):
                    chr, _, _ = start.partition("q")
                    end = f"{chr}{end}"
                # the range that sarts with a p needs
                # the chromosome moved over, like in
                # 1p34.2-p34.1
                elif end.startswith("p"):
                    chr, _, _ = start.partition("p")
                    end = f"{chr}{end}"

                if start not in location_to_chr:
                    unhandled_locations[start].add(identifier)
                elif end not in location_to_chr:
                    unhandled_locations[end].add(identifier)
                elif start in location_to_chr and end in location_to_chr:
                    term.append_relationship(
                        starts, location_to_chr[start], annotations=annotations
                    )
                    term.append_relationship(ends, location_to_chr[end], annotations=annotations)
                else:
                    unhandled_locations[location].add(identifier)
            else:
                unhandled_locations[location].add(identifier)

        locus_type = entry.pop("locus_type")
        # note that locus group is a more broad category than locus type,
        # and since we already have an exhaustive mapping from locus type
        # to SO, then we can throw this annotation away
        _locus_group = entry.pop("locus_group")
        so_id = LOCUS_TYPE_TO_SO.get(locus_type)
        if not so_id:
            raise ValueError("""\
                HGNC has updated their list of locus types, so the HGNC script is currently
                incomplete. This can be fixed by updating the ``LOCUS_TYPE_TO_SO`` dictionary
                to point to a new SO term. If there is none existing, then make a pull request
                to https://github.com/The-Sequence-Ontology/SO-Ontologies like in
                https://github.com/The-Sequence-Ontology/SO-Ontologies/pull/668. If the
                maintainers aren't responsive, you can still use the proposed term before it's
                accepted upstream like was done for SO:0003001 and SO:0003002
            """)

        term.append_parent(Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id)))
        term.set_species(identifier="9606", name="Homo sapiens")

        for key in entry:
            if key not in SKIP_KEYS:
                unhandled_entry_keys[key] += 1
        yield term

    if unhandled_locations:
        logger.warning(
            "Unhandled chromosomal locations:\n\n%s\n",
            tabulate(
                [(k, len(vs), f"HGNC:{min(vs)}") for k, vs in unhandled_locations.items()],
                headers=["location", "count", "example"],
                tablefmt="github",
            ),
        )

    if unhandled_entry_keys:
        logger.warning("Unhandled keys:\n%s", tabulate(unhandled_entry_keys.most_common()))


if __name__ == "__main__":
    HGNCGetter.cli()
