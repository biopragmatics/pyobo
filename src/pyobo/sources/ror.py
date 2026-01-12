"""Convert the Research Organization Registry (ROR) into an ontology."""

from __future__ import annotations

import datetime
import json
import logging
import zipfile
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NamedTuple, TypeAlias

import bioregistry
import zenodo_client
from pydantic import BaseModel, ValidationError
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

__all__ = [
    "OrganizationType",
    "RORStatus",
    "get_ror_records",
    "get_ror_status",
    "get_ror_to_country_geonames",
]

logger = logging.getLogger(__name__)
PREFIX = "ror"
ROR_ZENODO_RECORD_ID = "17953395"

# Constants
ORG_CLASS = Reference(prefix="OBI", identifier="0000245", name="organization")
CITY_CLASS = Reference(prefix="ENVO", identifier="00000856", name="city")

RMAP = {
    "related": see_also,
    "child": has_part,
    "parent": part_of,
    "predecessor": has_predecessor,
    "successor": has_successor,
    "located in": located_in,
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
        self.data_version, _url, _path = get_ror_status()
        super().__post_init__()

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield CHARLIE_TERM
        yield HUMAN_TERM
        yield Term(reference=ORG_CLASS)
        yield Term(reference=CITY_CLASS)
        yield from ROR_ORGANIZATION_TYPE_TO_OBI.values()
        yield from iterate_ror_terms(force=force)


OrganizationType: TypeAlias = Literal[
    "education",
    "facility",
    "funder",
    "company",
    "government",
    "healthcare",
    "archive",
    "nonprofit",
    "other",
]

ROR_ORGANIZATION_TYPE_TO_OBI: dict[OrganizationType, Term] = {
    "education": Term.default(PREFIX, "education", "educational organization"),
    "facility": Term.default(PREFIX, "facility", "facility"),
    "funder": Term.default(PREFIX, "funder", "funder"),
    "company": Term.default(PREFIX, "company", "company"),
    "government": Term.default(PREFIX, "government", "government organization"),
    "healthcare": Term.default(PREFIX, "healthcare", "healthcare organization"),
    "archive": Term.default(PREFIX, "archive", "archival organization"),
    "nonprofit": Term.default(PREFIX, "healthcare", "nonprofit organization")
    .append_xref(Reference(prefix="ICO", identifier="0000048"))
    .append_xref(Reference(prefix="GSSO", identifier="004615")),
}
for _k, v in ROR_ORGANIZATION_TYPE_TO_OBI.items():
    v.append_parent(ORG_CLASS)
    v.append_contributor(CHARLIE_TERM)
    v.append_comment(PYOBO_INJECTED)

_MISSED_ORG_TYPES: set[str] = set()


class LocationDetails(BaseModel):
    """The location details slot in the ROR schema."""

    continent_code: str
    continent_name: str
    country_code: str
    country_name: str
    country_subdivision_code: str | None = None
    country_subdivision_name: str | None = None
    lat: float
    lng: float
    name: str


class Location(BaseModel):
    """The lcoation slot in the ROR schema."""

    geonames_id: int
    geonames_details: LocationDetails


class ExternalID(BaseModel):
    """The external ID slot in the ROR schema."""

    type: str
    all: list[str]
    preferred: str | None = None


class Link(BaseModel):
    """The link slot in the ROR schema."""

    type: str
    value: str


class Name(BaseModel):
    """The name slot in the ROR schema."""

    value: str
    types: list[str]
    lang: str | None = None


class Relationship(BaseModel):
    """The relationship slot in the ROR schema."""

    type: str
    label: str
    id: str


class DateAnnotated(BaseModel):
    """The annotated date slot in the ROR schema."""

    date: datetime.date
    schema_version: str


class Admin(BaseModel):
    """The admin slot in the ROR schema."""

    created: DateAnnotated
    last_modified: DateAnnotated


Status: TypeAlias = Literal["active", "inactive", "withdrawn"]


class Record(BaseModel):
    """A ROR record."""

    locations: list[Location]
    established: int | None = None
    external_ids: list[ExternalID]
    id: str
    domains: list[str]
    links: list[Link]
    names: list[Name]
    relationships: list[Relationship]
    status: Status
    types: list[OrganizationType]
    admin: Admin

    def get_preferred_label(self) -> str | None:
        """Get the preferred label."""
        primary_name: str | None = None
        for name in self.names:
            if "ror_display" in name.types:
                primary_name = name.value
        if primary_name is None:
            return None
        primary_name = NAME_REMAPPING.get(primary_name, primary_name)
        return primary_name


_description_prefix = {
    "education": "an educational organization",
    "facility": "a facility",
    "funder": "a funder",
    "company": "a company",
    "government": "a governmental organization",
    "healthcare": "a healthcare organization",
    "archive": "an archive",
    "nonprofit": "a nonprofit organization",
    "other": "an organization",
}


def _get_description(record: Record) -> str | None:
    description = (
        f"{_description_prefix[record.types[0]]} in {record.locations[0].geonames_details.name}"
    )
    if record.established:
        description += f" established in {record.established}"
    return description


def iterate_ror_terms(*, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in ROR."""
    status, records = get_ror_records(force=force)
    unhandled_xref_prefixes: set[str] = set()

    seen_geonames_references = set()
    for record in tqdm(records, unit_scale=True, unit="record", desc=f"{PREFIX} v{status.version}"):
        identifier = record.id.removeprefix("https://ror.org/")

        primary_name = record.get_preferred_label()
        if primary_name is None:
            raise ValueError("should have got a primary name...")

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=primary_name),
            type="Instance",
            definition=_get_description(record),
        )
        for organization_type in record.types:
            if organization_type in ROR_ORGANIZATION_TYPE_TO_OBI:
                term.append_parent(ROR_ORGANIZATION_TYPE_TO_OBI[organization_type])
            else:
                term.append_parent(ORG_CLASS)

        for link in record.links:
            term.annotate_uri(has_homepage, link.value)

        if primary_name.startswith("The "):
            term.append_synonym(primary_name.removeprefix("The "))

        for relationship in record.relationships:
            target_id = relationship.id.removeprefix("https://ror.org/")
            term.append_relationship(
                RMAP[relationship.type], Reference(prefix=PREFIX, identifier=target_id)
            )

        if record.status != "active":
            term.is_obsolete = True

        for location in record.locations:
            geonames_reference = Reference(
                prefix="geonames",
                identifier=str(location.geonames_id),
                name=location.geonames_details.name,
            )
            seen_geonames_references.add(geonames_reference)
            term.append_relationship(RMAP["located in"], geonames_reference)

        for name in record.names:
            if "ror_display" in name.types:
                continue
            elif name.types == ["acronym"]:
                term.append_synonym(name.value, type=acronym)
            elif name.types == ["alias"]:
                synonym = name.value.strip().replace("\n", " ")
                term.append_synonym(synonym)
                if synonym.startswith("The "):
                    term.append_synonym(synonym.removeprefix("The "), language=name.lang)
            elif name.types == ["label"]:
                label = name.value.strip().replace("\n", " ")
                term.append_synonym(label, language=name.lang)
                if label.startswith("The "):
                    term.append_synonym(label.removeprefix("The "), language=name.lang)
            else:
                tqdm.write(
                    f"[ror:{identifier}] unhandled name types: {name.types} for {name.value}"
                )
                continue

        for external_id in record.external_ids:
            if external_id.type.lower() == "orgref":
                # OrgRef refers to wikipedia page id, see
                # https://stackoverflow.com/questions/6168020/what-is-wikipedia-pageid-how-to-change-it-into-real-page-url
                continue
            norm_prefix = bioregistry.normalize_prefix(external_id.type)
            xref_ids = external_id.all

            if norm_prefix is None:
                if external_id.type not in unhandled_xref_prefixes:
                    tqdm.write(
                        f"Unhandled prefix: {external_id.type} in {primary_name} ({term.curie}). Values:"
                    )
                    for xref_id in xref_ids:
                        tqdm.write(f"- {xref_id}")
                    unhandled_xref_prefixes.add(external_id.type)
                continue

            if isinstance(xref_ids, str):
                xref_ids = [xref_ids]
            for xref_id in xref_ids:
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


class RORStatus(NamedTuple):
    """A version information tuple."""

    version: str
    url: str
    path: Path


def get_ror_status(*, force: bool = False, authenticate_zenodo: bool = True) -> RORStatus:
    """Ensure the latest ROR record, metadata, and filepath.

    :param force: Should the record be downloaded again? This almost
        never needs to be true, since the data doesn't change for
        a given version
    :param authenticate_zenodo: Should Zenodo be authenticated?
        This isn't required, but can help avoid rate limits
    :return: A version information tuple

    .. note::

        this goes into the ``~/.data/zenodo/6347574`` folder,
        because 6347574 is the super-record ID, which groups all
        versions together. this is different from the value
        for :data:`ROR_ZENODO_RECORD_ID`
    """
    client = zenodo_client.Zenodo()
    latest_record_id = client.get_latest_record(
        ROR_ZENODO_RECORD_ID, authenticate=authenticate_zenodo
    )
    response = client.get_record(latest_record_id, authenticate=authenticate_zenodo)
    response_json = response.json()
    version = response_json["metadata"]["version"].lstrip("v")
    file_record = response_json["files"][0]
    name = file_record["key"]
    url = file_record["links"]["self"]
    path = client.download(latest_record_id, name=name, force=force)
    return RORStatus(version=version, url=url, path=path)


@lru_cache
def get_ror_records(
    *, force: bool = False, authenticate_zenodo: bool = True
) -> tuple[RORStatus, list[Record]]:
    """Get the latest ROR metadata and records."""
    status = get_ror_status(force=force, authenticate_zenodo=authenticate_zenodo)
    with zipfile.ZipFile(status.path) as zf:
        for zip_info in zf.filelist:
            if zip_info.filename.endswith(".json"):
                with zf.open(zip_info) as file:
                    records = [
                        Record.model_validate(record)
                        for record in tqdm(json.load(file), unit_scale=True)
                    ]
                    return status, records
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
