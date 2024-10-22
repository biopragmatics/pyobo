"""Parsers for MSig."""

import logging
from collections.abc import Iterable
from typing import Optional

from lxml.etree import ElementTree
from tqdm.auto import tqdm

from ..struct import Obo, Reference, Term, has_participant
from ..utils.path import ensure_path

logger = logging.getLogger(__name__)

__all__ = [
    "MSigDBGetter",
]

PREFIX = "msigdb"
BASE_URL = "https://data.broadinstitute.org/gsea-msigdb/msigdb/release"


class MSigDBGetter(Obo):
    """An ontology representation of MMSigDB's gene set nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_participant]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get MSIG as Obo."""
    return MSigDBGetter(force=force)


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


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get MSigDb terms."""
    xml_url = f"{BASE_URL}/{version}.Hs/msigdb_v{version}.Hs.xml"
    path = ensure_path(prefix=PREFIX, url=xml_url, version=version, force=force)
    tree = ElementTree.parse(path)

    for entry in tqdm(tree.getroot(), desc=f"{PREFIX} v{version}", unit_scale=True):
        attrib = dict(entry.attrib)
        tax_id = _SPECIES[attrib["ORGANISM"]]

        reference_id = attrib["PMID"].strip()
        if not reference_id:
            reference = None
        elif reference_id.startswith("GSE"):
            reference = Reference(prefix="gse", identifier=reference_id)
        else:
            reference = Reference(prefix="pubmed", identifier=reference_id)

        # NONE have the entry "HISTORICAL_NAME"
        # historical_name = thing.attrib['HISTORICAL_NAME']

        identifier = attrib["SYSTEMATIC_NAME"]
        name = attrib["STANDARD_NAME"]
        is_obsolete = attrib["CATEGORY_CODE"] == "ARCHIVED"

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=_get_definition(attrib),
            provenance=[] if reference is None else [reference],
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
            term.append_xref(Reference(prefix="wikipathways", identifier=external_id))
        elif contributor == "Reactome":
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference(prefix="reactome", identifier=external_id))
        elif contributor == "Gene Ontology":
            if not external_id:
                external_id = external_details[len(GO_URL_PREFIX) :]
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference(prefix="go", identifier=external_id))
        elif contributor == "KEGG":
            if not external_id:
                external_id = external_details[len(KEGG_URL_PREFIX) : len(".html")]
            if not external_id:
                logger.warning(
                    "missing %s source: msigdb:%s (%s)", contributor, identifier, external_details
                )
            term.append_xref(Reference(prefix="kegg.pathway", identifier=external_id))

        for ncbigene_id in attrib["MEMBERS_EZID"].strip().split(","):
            if ncbigene_id:
                term.append_relationship(
                    has_participant, Reference(prefix="ncbigene", identifier=ncbigene_id)
                )
        yield term


def _get_definition(attrib) -> Optional[str]:
    rv = attrib["DESCRIPTION_FULL"].strip() or attrib["DESCRIPTION_BRIEF"].strip() or None
    if rv is not None:
        return rv.replace(r"\d", "").replace(r"\s", "")
    return None


if __name__ == "__main__":
    MSigDBGetter.cli()
