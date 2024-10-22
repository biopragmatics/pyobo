"""Convert the Research Organization Registry (ROR) into an ontology."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable
from typing import Any

import bioregistry
import zenodo_client
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.struct import acronym
from pyobo.struct.typedef import (
    has_homepage,
    has_part,
    has_predecessor,
    has_successor,
    located_in,
    part_of,
    see_also,
)

PREFIX = "ror"
ROR_ZENODO_RECORD_ID = "10086202"

# Constants
ORG_CLASS = Reference(prefix="OBI", identifier="0000245")

RMAP = {
    "Related": see_also,
    "Child": has_part,
    "Parent": part_of,
    "Predecessor": has_predecessor,
    "Successor": has_successor,
    "Located in": located_in,
}
NAME_REMAPPING = {
    "'s-Hertogenbosch": "Den Bosch",  # SMH Netherlands, why u gotta be like this
    "'s Heeren Loo": "s Heeren Loo",
    "'s-Heerenberg": "s-Heerenberg",
    "Institut Virion\\Serion": "Institut Virion/Serion",
    "Hematology\\Oncology Clinic": "Hematology/Oncology Clinic",
}


class RORGetter(Obo):
    """An ontology representation of the ROR."""

    ontology = bioregistry_key = PREFIX
    typedefs = [has_homepage, *RMAP.values()]
    synonym_typedefs = [acronym]
    idspaces = {
        "ror": "https://ror.org/",
        "geonames": "https://www.geonames.org/",
        "ENVO": "http://purl.obolibrary.org/obo/ENVO_",
        "BFO": "http://purl.obolibrary.org/obo/BFO_",
        "RO": "http://purl.obolibrary.org/obo/RO_",
        "OBI": "http://purl.obolibrary.org/obo/OBI_",
        "OMO": "http://purl.obolibrary.org/obo/OMO_",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }

    def __post_init__(self):
        self.data_version, _url, _path = _get_info()
        super().__post_init__()

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_ror_terms(force=force)


ROR_ORGANIZATION_TYPE_TO_OBI = {
    "Education": ...,
    "Facility": ...,
    "Company": ...,
    "Government": ...,
    "Healthcare": ...,
    "Other": ...,
    "Archive": ...,
}
_MISSED_ORG_TYPES: set[str] = set()


def iterate_ror_terms(*, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in ROR."""
    version, source_uri, records = get_latest(force=force)
    unhandled_xref_prefixes = set()
    for record in tqdm(records, unit_scale=True, unit="record", desc=PREFIX):
        identifier = record["id"].removeprefix("https://ror.org/")
        name = record["name"]
        name = NAME_REMAPPING.get(name, name)

        organization_types = record.get("types", [])
        description = f"{organization_types[0]} in {record['country']['country_name']}"
        if established := record["established"]:
            description += f" established in {established}"

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            type="Instance",
            definition=description,
        )
        term.append_parent(ORG_CLASS)
        # TODO replace term.append_parent(ORG_CLASS) with:
        # for organization_type in organization_types:
        #     term.append_parent(ORG_PARENTS[organization_type])

        for link in record.get("links", []):
            term.append_property(has_homepage, link)

        if name.startswith("The "):
            term.append_synonym(name.removeprefix("The "))

        for relationship in record.get("relationships", []):
            target_id = relationship["id"].removeprefix("https://ror.org/")
            term.append_relationship(
                RMAP[relationship["type"]], Reference(prefix=PREFIX, identifier=target_id)
            )

        term.is_obsolete = record.get("status") != "active"

        for address in record.get("addresses", []):
            city = address.get("geonames_city")
            if not city:
                continue
            term.append_relationship(
                RMAP["Located in"], Reference(prefix="geonames", identifier=str(city["id"]))
            )

        for label in record.get("labels", []):
            label = label["label"]  # there's a language availabel in this dict too
            term.append_synonym(label)
            if label.startswith("The "):
                term.append_synonym(label.removeprefix("The "))

        for synonym in record.get("aliases", []):
            term.append_synonym(synonym)
            if synonym.startswith("The "):
                term.append_synonym(synonym.removeprefix("The "))

        for acronym_synonym in record.get("acronyms", []):
            term.append_synonym(acronym_synonym, type=acronym)

        for prefix, xref_data in record.get("external_ids", {}).items():
            if prefix == "OrgRef":
                # OrgRef refers to wikipedia page id, see
                # https://stackoverflow.com/questions/6168020/what-is-wikipedia-pageid-how-to-change-it-into-real-page-url
                continue
            norm_prefix = bioregistry.normalize_prefix(prefix)
            if norm_prefix is None:
                if prefix not in unhandled_xref_prefixes:
                    tqdm.write(f"Unhandled prefix: {prefix} in {name} ({term.curie}). Values:")
                    for xref_id in xref_data["all"]:
                        tqdm.write(f"- {xref_id}")
                    unhandled_xref_prefixes.add(prefix)
                continue

            identifiers = xref_data["all"]
            if isinstance(identifiers, str):
                identifiers = [identifiers]
            for xref_id in identifiers:
                term.append_xref(Reference(prefix=norm_prefix, identifier=xref_id.replace(" ", "")))

        yield term


def _get_info(*, force: bool = False):
    client = zenodo_client.Zenodo()
    latest_record_id = client.get_latest_record(ROR_ZENODO_RECORD_ID)
    response = client.get_record(latest_record_id)
    response_json = response.json()
    version = response_json["metadata"]["version"].lstrip("v")
    file_record = response_json["files"][0]
    name = file_record["key"]
    url = file_record["links"]["self"]
    path = client.download(latest_record_id, name=name, force=force)
    return version, url, path


def get_latest(*, force: bool = False):
    """Get the latest ROR metadata and records."""
    version, url, path = _get_info(force=force)
    with zipfile.ZipFile(path) as zf:
        for zip_info in zf.filelist:
            if zip_info.filename.endswith(".json"):
                with zf.open(zip_info) as file:
                    return version, url, json.load(file)
    raise FileNotFoundError


def get_ror_to_country_geonames(**kwargs: Any) -> dict[str, str]:
    """Get a mapping of ROR ids to GeoNames IDs for countries."""
    from pyobo.sources.geonames import get_city_to_country

    city_to_country = get_city_to_country()
    rv = {}
    for term in iterate_ror_terms(**kwargs):
        city_geonames_reference = term.get_relationship(located_in)
        if city_geonames_reference is None:
            continue
        if city_geonames_reference.identifier in city_to_country:
            rv[term.identifier] = city_to_country[city_geonames_reference.identifier]
    return rv


if __name__ == "__main__":
    RORGetter(force=True).write_default(write_obo=True, force=True)
