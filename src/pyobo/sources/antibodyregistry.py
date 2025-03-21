"""Converter for the Antibody Registry."""

import json
import logging
from collections.abc import Iterable, Mapping

import lxml.html
import pystow
from httpx import Client, Timeout, Cookies, URL as HTTPX_URL, RequestError
from pystow import ConfigError

from bioregistry.utils import removeprefix
from tqdm.auto import tqdm

from curies import Prefix
from pyobo import Obo, Reference, Term
from pyobo.constants import RAW_MODULE
from pyobo.struct.typedef import has_citation

__all__ = [
    "AntibodyRegistryGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "antibodyregistry"
BASE_URL = "https://www.antibodyregistry.org/api/antibodies"
PAGE_SIZE = 10000
TIMEOUT = 180.0
RAW_DATA_MODULE = RAW_MODULE.module(PREFIX)
RAW_DATA_PARTS = RAW_DATA_MODULE.module("parts")
RAW_CACHE = RAW_DATA_MODULE.base.joinpath("results.json")


class AntibodyRegistryGetter(Obo):
    """An ontology representation of the Antibody Registry."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_citation]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(force: bool = False, retries: int = 4) -> Iterable[Term]:
    """Get Antibody Registry terms."""
    # From experience, errors typically happen about one hour after the first request,
    # so with < 400 pages 4 retries should be enough.
    raw_data = []
    for i in range(max(1, retries)):
        try:
            raw_data = get_data(force=force)
            break
        except RequestError:
            if i == retries - 1:
                logger.error("Too many retries failed for Antibody Registry.")
                raise
            continue

    needs_curating = set()
    for item in raw_data:
        term = _get_term(item, needs_curating=needs_curating)
        yield term


# TODO there are tonnnnsss of mappings to be curated
MAPPING: Mapping[str, str | None] = {
    "AMERICAN DIAGNOSTICA": None,  # No website
    "Biolegend": "biolegend",
    "Enzo Life Sciences": "enzo",
    "Novus": "novus",
    "LifeSpan": "biozil",
    "Creative Diagnostics": None,  # This site doesn't have a provider for IDs
}

SKIP = {
    "Universi",
    "School",
    "201",
    "200",
    "199",
}


def _get_term(
    json_data: dict[str, None | str | list[str]], needs_curating: set
) -> Term:
    # todo: makes use of more fields in the JSON? All fields:
    #  catalogNum, vendorName, clonality, epitope, comments, url, abName,
    #  abTarget, cloneId, commercialType, definingCitation, productConjugate,
    #  productForm, productIsotype, sourceOrganism, targetSpecies, uniprotId,
    #  applications, kitContents, abTargetEntrezId, abTargetUniprotId,
    #  numOfCitation, accession, status, feedback, abId, catAlt, curateTime,
    #  curatorComment, discDate, insertTime, targetModification,
    #  targetSubregion, vendorId, lastEditTime, ix, showLink, vendorUrl
    identifier = json_data["abId"]
    name = json_data["abName"]
    vendor = json_data["vendorName"]
    catalog_number = json_data["catalogNum"]
    defining_citation = json_data["definingCitation"]
    term = Term.from_triple(prefix=PREFIX, identifier=identifier, name=name)

    if vendor not in MAPPING:
        if vendor not in needs_curating:
            needs_curating.add(vendor)
            if all(x not in vendor for x in SKIP):
                logger.debug(f"! vendor {vendor} for {identifier}")
    elif MAPPING[vendor] is not None and catalog_number:
        term.append_xref((MAPPING[vendor], catalog_number))
    if defining_citation:
        for pubmed_id in defining_citation.split(","):
            pubmed_id = removeprefix(pubmed_id.strip(), prefix="PMID:").strip()
            if not pubmed_id:
                continue
            term.append_provenance(
                Reference(prefix=Prefix("pubmed"), identifier=pubmed_id, name=None)
            )
    return term


def get_data(
    max_pages: int | None = None,
    page_size: int = PAGE_SIZE,
    force: bool = False,
    timeout: float = TIMEOUT,
) -> list[dict[str, str | None | list[str]]]:
    # identifier, name, vendor, catalog_number, defining_citation
    """Iterate over terms in the Antibody Registry."""
    if RAW_CACHE.is_file() and not force:
        # load cache
        with open(RAW_CACHE) as file:
            return json.load(file)

    # Check for existing parts, sort in ascending order of filename
    parts = sorted((p for p in RAW_DATA_PARTS.base.glob("page*json")), key=lambda x: x.name)

    # Get first non-existing page, unless we force
    existing_pages = {int(p.stem.removeprefix("page")) for p in parts} if not force else set()
    if not existing_pages:
        # No existing pages, start from page 1
        first_page = 1
    else:
        # Find the first missing page
        logger.info(f"Found {len(existing_pages)} existing pages.")
        first_page = min(set(range(1, max(existing_pages) + 2)) - existing_pages)

    # Get first missing page
    cookies = antibodyregistry_login(timeout=timeout)
    with Client(http2=True, timeout=Timeout(timeout)) as client:
        r = client.get(
            HTTPX_URL(BASE_URL),
            cookies=cookies,
            params={"page": first_page, "size": PAGE_SIZE},
        )
        r.raise_for_status()
        res_json = r.json()

        # Write the first page to the cache
        with RAW_DATA_PARTS.base.joinpath(f"page{first_page}.json").open("w") as file:
            json.dump(res_json["items"], file)

        # Get max page and calculate total pages left after first page
        total_count = res_json["totalElements"]
        total_pages = total_count // PAGE_SIZE + (1 if total_count % PAGE_SIZE else 0)
        if len(res_json["items"]) != PAGE_SIZE:
            logger.error("The first page does not have the expected number of items.")
            raise ValueError(
                f"Number of items on the first page is not {PAGE_SIZE}. "
                f"Recommending reduce page_size."
            )

        # Now, iterate over the remaining pages
        for page in tqdm(
            range(1, total_pages),
            desc=f"{PREFIX}, page size={PAGE_SIZE}",
            total=total_pages,
        ):
            # Skip if the page already exists, unless we are forcing
            part_file = RAW_DATA_PARTS.base.joinpath(f"page{page}.json")
            if part_file.is_file() and not force:
                continue

            r = client.get(
                HTTPX_URL(BASE_URL),
                cookies=cookies,
                params={"page": page, "size": PAGE_SIZE},
            )
            r.raise_for_status()
            res_json = r.json()
            with part_file.open("w") as file:
                json.dump(res_json["items"], file)

    # Now merge all the pages
    cache = []
    for page in RAW_DATA_PARTS.base.glob("page*json"):
        with page.open("r") as file:
            cache.extend(json.load(file))
    return cache


def antibodyregistry_login(timeout: float = TIMEOUT) -> Cookies:
    """Login to Antibody Registry."""
    logger.info("Logging in to Antibody Registry")
    try:
        username = pystow.get_config(
            "pyobo", "antibodyregistry_username", raise_on_missing=True
        )
        password = pystow.get_config(
            "pyobo", "antibodyregistry_password", raise_on_missing=True
        )
    except ConfigError:
        logger.error(
            "You must register at https://www.antibodyregistry.org to use this source."
        )
        raise

    with Client(
        follow_redirects=True,
        http2=True,
        timeout=Timeout(timeout),
    ) as client:
        r = client.get(HTTPX_URL("https://www.antibodyregistry.org/login"))
        r.raise_for_status()

        cookies = r.cookies
        tree = lxml.html.fromstring(r.content)
        login_post_url = HTTPX_URL(tree.xpath('//form[@id="kc-form-login"]/@action')[0])

        r = client.post(
            login_post_url,
            cookies=cookies,
            data={
                "username": username,
                "password": password,
                "rememberMe": "on",
                "credentialId": "",
            },
        )
        r.raise_for_status()

        cookies = r.history[1].cookies
        return cookies


if __name__ == "__main__":
    AntibodyRegistryGetter.cli()
