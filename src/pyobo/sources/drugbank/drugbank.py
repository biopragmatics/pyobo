"""Convert DrugBank to OBO.

Run with ``python -m pyobo.sources.drugbank``
"""

import datetime
import itertools as itt
import logging
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree

import pystow
from tqdm.auto import tqdm

from ...getters import NoBuildError
from ...struct import Obo, Reference, Term
from ...struct.typedef import has_inchi, has_salt, has_smiles
from ...utils.cache import cached_pickle
from ...utils.path import prefix_directory_join

__all__ = [
    "DrugBankGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "drugbank"


class DrugBankGetter(Obo):
    """A getter for DrugBank."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_salt]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


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
    term = Term.from_triple(
        prefix=PREFIX,
        identifier=drug_info["drugbank_id"],
        name=drug_info["name"],
    )
    definition = drug_info.get("description")
    if definition:
        definition = definition.strip('"').replace("\t", " ").replace("  ", " ")
        term.definition = definition

    for alias in drug_info["aliases"]:
        term.append_synonym(alias)

    for xref in drug_info["xrefs"]:
        xref_prefix, xref_identifier = xref["resource"], xref["identifier"]
        if xref_prefix in DRUG_XREF_SKIP:
            continue
        xref_prefix_norm = DRUG_XREF_MAPPING.get(xref_prefix)
        if xref_prefix_norm is None:
            logger.warning("unhandled xref: %s:%s", xref_prefix, xref_identifier)
            continue
        term.append_xref(Reference(prefix=xref_prefix_norm, identifier=xref_identifier))

    for xref_prefix in ["cas", "inchikey"]:
        identifier = drug_info.get(xref_prefix)
        if identifier:
            term.append_xref(Reference(prefix=xref_prefix, identifier=identifier))

    for key, typedef_ in [("smiles", has_smiles), ("inchi", has_inchi)]:
        identifier = drug_info.get(key)
        if identifier:
            term.annotate_string(typedef_, identifier)

    for salt in drug_info.get("salts", []):
        term.annotate_object(
            has_salt,
            Reference(
                prefix="drugbank.salt",
                identifier=salt["identifier"],
                name=salt["name"],
            ),
        )

    return term


@lru_cache
def get_xml_root(version: str | None = None) -> ElementTree.Element:
    """Get the DrugBank XML parser root.

    Takes between 35-60 seconds.
    """
    from drugbank_downloader import parse_drugbank
    from pystow.config_api import ConfigError

    try:
        username = pystow.get_config("pyobo", "drugbank_username", raise_on_missing=True)
        password = pystow.get_config("pyobo", "drugbank_password", raise_on_missing=True)
    except ConfigError as e:
        raise NoBuildError from e

    element = parse_drugbank(version=version, username=username, password=password)
    return element.getroot()


ns = "{http://www.drugbank.ca}"
inchikey_template = f"{ns}calculated-properties/{ns}property[{ns}kind='InChIKey']/{ns}value"
inchi_template = f"{ns}calculated-properties/{ns}property[{ns}kind='InChI']/{ns}value"
smiles_template = f"{ns}calculated-properties/{ns}property[{ns}kind='SMILES']/{ns}value"


def _extract_drug_info(drug_xml: ElementTree.Element) -> Mapping[str, Any]:
    """Extract information from an XML element representing a drug."""
    # assert drug_xml.tag == f'{ns}drug'
    row: dict[str, Any] = {
        "type": drug_xml.get("type"),
        "drugbank_id": drug_xml.findtext(f"{ns}drugbank-id[@primary='true']"),
        "cas": drug_xml.findtext(f"{ns}cas-number"),
        "name": drug_xml.findtext(f"{ns}name"),
        "groups": [group.text for group in drug_xml.findall(f"{ns}groups/{ns}group")],
        "atc_codes": [code.get("code") for code in drug_xml.findall(f"{ns}atc-codes/{ns}atc-code")],
        "categories": [
            {
                "name": x.findtext(f"{ns}category"),
                "mesh_id": x.findtext(f"{ns}mesh-id"),
            }
            for x in drug_xml.findall(f"{ns}categories/{ns}category")
        ],
        "patents": list(_get_patents(drug_xml)),
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

    description = drug_xml.findtext(f"{ns}description")
    if description:
        row["description"] = description.replace("\r", "").replace("\n", "\\n")

    # Add drug aliases
    aliases = {
        elem.text.strip()
        for elem in itt.chain(
            drug_xml.findall(f"{ns}international-brands/{ns}international-brand"),
            drug_xml.findall(f"{ns}synonyms/{ns}synonym[@language='English']"),
            drug_xml.findall(f"{ns}international-brands/{ns}international-brand"),
            drug_xml.findall(f"{ns}products/{ns}product/{ns}name"),
        )
        if elem.text and elem.text.strip()
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


def _get_patents(drug_element):
    for patent_element in drug_element.findall(f"{ns}patents/{ns}patent"):
        rv = {
            "patent_id": patent_element.findtext(f"{ns}number"),
            "country": patent_element.findtext(f"{ns}country"),
            "pediatric_extension": patent_element.findtext(f"{ns}pediatric-extension") != "false",
        }
        approved = patent_element.findtext(f"{ns}approved")
        if approved is not None:
            rv["approved"] = datetime.datetime.strptime(approved, "%Y-%m-%d")
        expires = patent_element.findtext(f"{ns}expires")
        if expires:
            rv["expires"] = datetime.datetime.strptime(expires, "%Y-%m-%d")
        yield rv


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
    DrugBankGetter.cli()
