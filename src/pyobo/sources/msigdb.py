# -*- coding: utf-8 -*-

"""Parsers for MSig."""

import logging
from typing import Iterable, Optional
from xml.etree import ElementTree

import bioversions
import click
from more_click import verbose_option
from tqdm import tqdm

from ..struct import Obo, Reference, Term, has_part
from ..utils.path import ensure_path

logger = logging.getLogger(__name__)

PREFIX = "msigdb"
BASE_URL = "https://data.broadinstitute.org/gsea-msigdb/msigdb/release"


def get_obo() -> Obo:
    """Get MSIG as Obo."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name="Molecular Signatures Database",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
        typedefs=[has_part],
    )


_SPECIES = {
    "Homo sapiens": "9606",
    "Mus musculus": "10090",
    "Rattus norvegicus": "10116",
    "Macaca mulatta": "9544",
    "Danio rerio": "7955",
}

REACTOME_URL_PREFIX = "https://www.reactome.org/content/detail/"
GO_URL_PREFIX = "http://amigo.geneontology.org/amigo/term/GO:"
KEGG_URL_PREFIX = "http://www.genome.jp/kegg/pathway/hsa/"


def iter_terms(version: str) -> Iterable[Term]:
    """Get MSigDb terms."""
    xml_url = f"{BASE_URL}/{version}/msigdb_v{version}.xml"
    path = ensure_path(prefix=PREFIX, url=xml_url, version=version)
    tree = ElementTree.parse(path)

    for entry in tqdm(tree.getroot(), desc=f"{PREFIX} v{version}"):
        attrib = dict(entry.attrib)
        tax_id = _SPECIES[attrib["ORGANISM"]]

        reference_id = attrib["PMID"].strip()
        if not reference_id:
            reference = None
        elif reference_id.startswith("GSE"):
            reference = Reference("gse", reference_id)
        else:
            reference = Reference("pubmed", reference_id)

        # NONE have the entry "HISTORICAL_NAME"
        # historical_name = thing.attrib['HISTORICAL_NAME']

        identifier = attrib["SYSTEMATIC_NAME"]
        name = attrib["STANDARD_NAME"]
        is_obsolete = attrib["CATEGORY_CODE"] == "ARCHIVED"

        term = Term(
            reference=Reference(PREFIX, identifier, name),
            definition=_get_definition(attrib),
            provenance=reference and [reference],
            is_obsolete=is_obsolete,
        )
        for key in [
            "CATEGORY_CODE",
            "SUB_CATEGORY_CODE",
            "CONTRIBUTOR",
            "EXACT_SOURCE",
            "EXTERNAL_DETAILS_URL",
        ]:
            value = attrib[key].strip()
            if value:
                term.append_property(key.lower(), value)

        term.set_species(tax_id)

        contributor = attrib["CONTRIBUTOR"]
        external_id = attrib["EXACT_SOURCE"]
        external_details = attrib["EXTERNAL_DETAILS_URL"]
        if contributor == "WikiPathways":
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference("wikipathways", external_id))
        elif contributor == "Reactome":
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference("reactome", external_id))
        elif contributor == "Gene Ontology":
            if not external_id:
                external_id = external_details[len(GO_URL_PREFIX) :]
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference("go", external_id))
        elif contributor == "KEGG":
            if not external_id:
                external_id = external_details[len(KEGG_URL_PREFIX) : len(".html")]
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference("kegg.pathway", external_id))

        for ncbigene_id in attrib["MEMBERS_EZID"].strip().split(","):
            if ncbigene_id:
                term.append_relationship(
                    has_part, Reference(prefix="ncbigene", identifier=ncbigene_id)
                )
        yield term


def _get_definition(attrib) -> Optional[str]:
    rv = attrib["DESCRIPTION_FULL"].strip() or attrib["DESCRIPTION_BRIEF"].strip() or None
    if rv is not None:
        return rv.replace("\d", "").replace("\s", "")  # noqa: W605


@click.command()
@verbose_option
def _main():
    get_obo().write_default(force=True)


if __name__ == "__main__":
    _main()
