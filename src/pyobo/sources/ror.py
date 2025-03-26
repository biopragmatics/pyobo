"""Convert the Research Organization Registry (ROR) into an ontology."""

from __future__ import annotations

import json
import logging
import zipfile
from collections.abc import Iterable
from typing import Any

import bioregistry
import zenodo_client
from pydantic import ValidationError
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED, acronym
from pyobo.struct.typedef import (
    has_homepage,
    has_part,
    has_predecessor,
    has_successor,
    located_in,
    part_of,
    see_also,
)

logger = logging.getLogger(__name__)
PREFIX = "ror"
ROR_ZENODO_RECORD_ID = "10086202"

# Constants
ORG_CLASS = Reference(prefix="OBI", identifier="0000245", name="organization")
CITY_CLASS = Reference(prefix="ENVO", identifier="00000856", name="city")

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
    root_terms = [CITY_CLASS, ORG_CLASS]

    def __post_init__(self):
        self.data_version, _url, _path = _get_info()
        super().__post_init__()

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield CHARLIE_TERM
        yield HUMAN_TERM
        yield Term(reference=ORG_CLASS)
        yield Term(reference=CITY_CLASS)
        yield from ROR_ORGANIZATION_TYPE_TO_OBI.values()
        yield from iterate_ror_terms(force=force)


ROR_ORGANIZATION_TYPE_TO_OBI: dict[str, Term] = {
    "Education": Term.default(PREFIX, "education", "educational organization"),
    "Facility": Term.default(PREFIX, "facility", "facility"),
    "Company": Term.default(PREFIX, "company", "company"),
    "Government": Term.default(PREFIX, "government", "government organization"),
    "Healthcare": Term.default(PREFIX, "healthcare", "healthcare organization"),
    "Archive": Term.default(PREFIX, "archive", "archival organization"),
    "Nonprofit": Term.default(PREFIX, "healthcare", "nonprofit organization")
    .append_xref(Reference(prefix="ICO", identifier="0000048"))
    .append_xref(Reference(prefix="GSSO", identifier="004615")),
}
for _k, v in ROR_ORGANIZATION_TYPE_TO_OBI.items():
    v.append_parent(ORG_CLASS)
    v.append_contributor(CHARLIE_TERM)
    v.append_comment(PYOBO_INJECTED)

_MISSED_ORG_TYPES: set[str] = set()


def iterate_ror_terms(*, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in ROR."""
    _version, _source_uri, records = get_latest(force=force)
    unhandled_xref_prefixes: set[str] = set()

    seen_geonames_references = set()
    for record in tqdm(records, unit_scale=True, unit="record", desc=f"{PREFIX} v{_version}"):
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
        for organization_type in organization_types:
            if organization_type == "Other":
                term.append_parent(ORG_CLASS)
            else:
                term.append_parent(ROR_ORGANIZATION_TYPE_TO_OBI[organization_type])

        for link in record.get("links", []):
            term.annotate_uri(has_homepage, link)

        if name.startswith("The "):
            term.append_synonym(name.removeprefix("The "))

        for relationship in record.get("relationships", []):
            target_id = relationship["id"].removeprefix("https://ror.org/")
            term.append_relationship(
                RMAP[relationship["type"]], Reference(prefix=PREFIX, identifier=target_id)
            )

        if record.get("status") != "active":
            term.is_obsolete = True

        for address in record.get("addresses", []):
            city = address.get("geonames_city")
            if not city:
                continue
            geonames_reference = Reference(
                prefix="geonames", identifier=str(city["id"]), name=city["city"]
            )
            seen_geonames_references.add(geonames_reference)
            term.append_relationship(RMAP["Located in"], geonames_reference)

        for label_dict in record.get("labels", []):
            label = label_dict["label"]
            label = label.strip().replace("\n", " ")
            language = label_dict["iso639"]
            term.append_synonym(label, language=language)
            if label.startswith("The "):
                term.append_synonym(label.removeprefix("The "), language=language)

        for synonym in record.get("aliases", []):
            synonym = synonym.strip().replace("\n", " ")
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
                xref_id = xref_id.replace(" ", "")
                try:
                    xref = Reference(prefix=norm_prefix, identifier=xref_id)
                except ValidationError:
                    tqdm.write(f"[{term.curie}] invalid xref: {norm_prefix}:{xref_id}")
                else:
                    term.append_xref(xref)

        yield term

    for geonames_ref in sorted(seen_geonames_references):
        geonames_term = Term(reference=geonames_ref, type="Instance")
        geonames_term.append_parent(CITY_CLASS)
        yield geonames_term


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
    from pyobo.sources.geonames.geonames import get_city_to_country

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
    RORGetter.cli()
