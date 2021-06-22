# -*- coding: utf-8 -*-

"""Convert DrugBank to OBO.

Run with ``python -m pyobo.sources.drugbank``
"""

import datetime
import itertools as itt
import logging
from functools import lru_cache
from typing import Any, Iterable, Mapping, Optional
from xml.etree import ElementTree

import bioversions
import pystow
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, Term, TypeDef
from ..utils.cache import cached_pickle
from ..utils.path import prefix_directory_join

logger = logging.getLogger(__name__)

PREFIX = "drugbank"

has_salt = TypeDef(
    reference=Reference.default(identifier="has_salt", name="has salt"),
)


def get_obo(force: bool = False) -> Obo:
    """Get DrugBank as OBO."""
    version = bioversions.get_version("drugbank")
    return Obo(
        ontology=PREFIX,
        name="DrugBank",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version, force=force),
        auto_generated_by=f"bio2obo:{PREFIX}",
        typedefs=[has_salt],
    )


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over DrugBank terms in OBO."""
    for drug_info in iterate_drug_info(version, force=force):
        yield _make_term(drug_info)


def iterate_drug_info(version: str, force: bool = False) -> Iterable[Mapping[str, Any]]:
    """Iterate over DrugBank records."""

    @cached_pickle(
        prefix_directory_join(PREFIX, name="precompiled.pkl", version=version), force=force
    )
    def _inner():
        root = get_xml_root(version)
        rv = [_extract_drug_info(drug_xml) for drug_xml in tqdm(root, desc="Drugs")]
        return rv

    return _inner()


DRUG_XREF_SKIP = {
    "Wikipedia",
    "PDB",
    "Drugs Product Database (DPD)",  # TODO needs curating in metaregistry
    "RxCUI",  # TODO needs curating in metaregistry
    "GenBank",  # about protein
    "UniProtKB",  # about protein
    "Guide to Pharmacology",  # redundant of
}

DRUG_XREF_MAPPING = {
    "PubChem Compound": "pubchem.compound",
    "PubChem Substance": "pubchem.substance",
    "ChEBI": "chebi",
    "KEGG Drug": "kegg.drug",
    "KEGG Compound": "kegg.compound",
    "ChemSpider": "chemspider",
    "ChEMBL": "chembl.compound",
    "ZINC": "zinc",
    "BindingDB": "bindingdb",
    "PharmGKB": "pharmgkb.drug",
    "Therapeutic Targets Database": "ttd.drug",
    "IUPHAR": "iuphar.ligand",
}


def _make_term(drug_info: Mapping[str, Any]) -> Term:
    xrefs = []
    for xref in drug_info["xrefs"]:
        xref_prefix, xref_identifier = xref["resource"], xref["identifier"]
        if xref_prefix in DRUG_XREF_SKIP:
            continue
        xref_prefix_norm = DRUG_XREF_MAPPING.get(xref_prefix)
        if xref_prefix_norm is None:
            logger.warning("unhandled xref: %s:%s", xref_prefix, xref_identifier)
            continue
        xrefs.append(Reference(prefix=xref_prefix_norm, identifier=xref_identifier))

    xrefs.append(Reference(prefix="cas", identifier=drug_info["cas_number"]))

    for k in ["inchi", "inchikey", "smiles"]:
        identifier = drug_info.get(k)
        if identifier is not None:
            xrefs.append(Reference(prefix=k, identifier=identifier))

    term = Term(
        reference=Reference(
            prefix=PREFIX, identifier=drug_info["drugbank_id"], name=drug_info["name"]
        ),
        definition=drug_info["description"],
        xrefs=xrefs,
        synonyms=[Synonym(name=alias) for alias in drug_info["aliases"]],
    )

    for salt in drug_info.get("salts", []):
        term.append_relationship(
            has_salt,
            Reference(
                prefix="drugbank.salt",
                identifier=salt["identifier"],
                name=salt["name"],
            ),
        )

    return term


@lru_cache()
def get_xml_root(version: Optional[str] = None) -> ElementTree.Element:
    """Get the DrugBank XML parser root.

    Takes between 35-60 seconds.
    """
    from drugbank_downloader import parse_drugbank

    return parse_drugbank(
        version=version,
        username=pystow.get_config("pyobo", "drugbank_username"),
        password=pystow.get_config("pyobo", "drugbank_password"),
    )


ns = "{http://www.drugbank.ca}"
inchikey_template = f"{ns}calculated-properties/{ns}property[{ns}kind='InChIKey']/{ns}value"
inchi_template = f"{ns}calculated-properties/{ns}property[{ns}kind='InChI']/{ns}value"
smiles_template = f"{ns}calculated-properties/{ns}property[{ns}kind='SMILES']/{ns}value"


def _extract_drug_info(drug_xml: ElementTree.Element) -> Mapping[str, Any]:
    """Extract information from an XML element representing a drug."""
    # assert drug_xml.tag == f'{ns}drug'
    row = {
        "type": drug_xml.get("type"),
        "drugbank_id": drug_xml.findtext(f"{ns}drugbank-id[@primary='true']"),
        "cas_number": drug_xml.findtext(f"{ns}cas-number"),
        "name": drug_xml.findtext(f"{ns}name"),
        "description": drug_xml.findtext(f"{ns}description").replace("\r", "").replace("\n", "\\n"),
        "groups": [group.text for group in drug_xml.findall(f"{ns}groups/{ns}group")],
        "atc_codes": [code.get("code") for code in drug_xml.findall(f"{ns}atc-codes/{ns}atc-code")],
        "categories": [
            {
                "name": x.findtext(f"{ns}category"),
                "mesh_id": x.findtext(f"{ns}mesh-id"),
            }
            for x in drug_xml.findall(f"{ns}categories/{ns}category")
        ],
        "patents": [
            {
                "patent_id": x.findtext(f"{ns}number"),
                "country": x.findtext(f"{ns}country"),
                "approved": datetime.datetime.strptime(x.findtext(f"{ns}approved"), "%Y-%m-%d"),
                "expires": datetime.datetime.strptime(x.findtext(f"{ns}expires"), "%Y-%m-%d"),
                "pediatric_extension": x.findtext(f"{ns}pediatric-extension") != "false",
            }
            for x in drug_xml.findall(f"{ns}patents/{ns}patent")
        ],
        "salts": [
            {
                "identifier": x.findtext(f"{ns}drugbank-id"),
                "name": x.findtext(f"{ns}name"),
                "unii": x.findtext(f"{ns}unii"),
                "cas": x.findtext(f"{ns}cas-number"),
                "inchikey": x.findtext(f"{ns}inchikey"),
            }
            for x in drug_xml.findall(f"{ns}salts/{ns}salt")
        ],
        "xrefs": [
            {
                "resource": x.findtext(f"{ns}resource"),
                "identifier": x.findtext(f"{ns}identifier"),
            }
            for x in drug_xml.findall(f"{ns}external-identifiers/{ns}external-identifier")
        ],
        "inchi": drug_xml.findtext(inchi_template),
        "inchikey": drug_xml.findtext(inchikey_template),
        "smiles": drug_xml.findtext(smiles_template),
    }

    # Add drug aliases
    aliases = {
        elem.text.strip()
        for elem in itt.chain(
            drug_xml.findall(f"{ns}international-brands/{ns}international-brand"),
            drug_xml.findall(f"{ns}synonyms/{ns}synonym[@language='English']"),
            drug_xml.findall(f"{ns}international-brands/{ns}international-brand"),
            drug_xml.findall(f"{ns}products/{ns}product/{ns}name"),
        )
        if elem.text.strip()
    }
    aliases.add(row["name"])
    row["aliases"] = aliases

    row["protein_interactions"] = []
    row["protein_group_interactions"] = []

    for category, protein in _iterate_protein_stuff(drug_xml):
        target_row = _extract_protein_info(category, protein)
        if not target_row:
            continue
        row["protein_interactions"].append(target_row)

    return row


_categories = ["target", "enzyme", "carrier", "transporter"]


def _iterate_protein_stuff(drug_xml):
    for category in _categories:
        proteins = drug_xml.findall(f"{ns}{category}s/{ns}{category}")
        for protein in proteins:
            yield category, protein


def _extract_protein_info(category, protein):
    # FIXME Differentiate between proteins and protein groups/complexes
    polypeptides = protein.findall(f"{ns}polypeptide")

    if len(polypeptides) == 0:
        protein_type = "none"
    elif len(polypeptides) == 1:
        protein_type = "single"
    else:
        protein_type = "group"

    row = {
        "target": {
            "type": protein_type,
            "category": category,
            "known_action": protein.findtext(f"{ns}known-action"),
            "name": protein.findtext(f"{ns}name"),
            "actions": [action.text for action in protein.findall(f"{ns}actions/{ns}action")],
            "articles": [
                pubmed_element.text
                for pubmed_element in protein.findall(
                    f"{ns}references/{ns}articles/{ns}article/{ns}pubmed-id"
                )
                if pubmed_element.text
            ],
        },
        "polypeptides": list(_iter_polypeptides(polypeptides)),
    }
    return row


def _iter_polypeptides(polypeptides) -> Iterable[Mapping[str, Any]]:
    for polypeptide in polypeptides:
        name = polypeptide.findtext(f"{ns}name")

        uniprot_id = polypeptide.findtext(
            f"{ns}external-identifiers/{ns}external-identifier[{ns}resource='UniProtKB']/{ns}identifier",
        )
        uniprot_accession = polypeptide.findtext(
            f"{ns}external-identifiers/{ns}external-identifier[{ns}resource='UniProt Accession']/{ns}identifier",
        )
        organism = polypeptide.findtext(f"{ns}organism")
        taxonomy_id = polypeptide.find(f"{ns}organism").attrib["ncbi-taxonomy-id"]

        yv = {
            "name": name,
            "uniprot_id": uniprot_id,
            "uniprot_accession": uniprot_accession,
            "organism": organism,
            "taxonomy": taxonomy_id,
        }

        hgnc_id = polypeptide.findtext(
            f"{ns}external-identifiers/{ns}external-identifier"
            f"[{ns}resource='HUGO Gene Nomenclature Committee (HGNC)']/{ns}identifier",
        )
        if hgnc_id is not None:
            hgnc_id = hgnc_id[len("HGNC:") :]
            yv["hgnc_id"] = hgnc_id
            yv["hgnc_symbol"] = polypeptide.findtext(f"{ns}gene-name")

        yield yv


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    get_obo().write_default()
