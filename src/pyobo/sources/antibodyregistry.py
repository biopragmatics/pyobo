"""Converter for the Antibody Registry."""

import json
import logging
from collections.abc import Iterable, Mapping

import lxml.html
import pystow
from httpx import Client, Timeout, Cookies, URL as HTTPX_URL
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
RAW_CACHE = RAW_DATA_MODULE.base.joinpath("results.json")


class AntibodyRegistryGetter(Obo):
    """An ontology representation of the Antibody Registry."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_citation]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Get Antibody Registry terms."""
    raw_data = get_data(force=force)
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
    max_pages: int = None,
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

    cache = []
    cookies = antibodyregistry_login(timeout=timeout)
    with Client(http2=True, timeout=Timeout(timeout)) as client:
        r = client.get(
            HTTPX_URL(BASE_URL),
            cookies=cookies,
            params={"page": 1, "size": page_size},
        )
        r.raise_for_status()
        res_json = r.json()

        # Get max page and calculate total pages left after first page
        total_count = res_json["totalElements"]
        total_pages = (
            (total_count // page_size) + 1 if total_count % page_size > 0 else 0
        )
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)
        if len(res_json["items"]) != page_size:
            logger.error("The first page does not have the expected number of items.")
            raise ValueError(
                f"Number of items on the first page is not {page_size}. "
                f"Recommending reduce page_size."
            )

        cache.append(res_json["items"])

        # Now, iterate over the remaining pages
        for page in tqdm(
            range(2, total_pages + 1),
            desc=f"{PREFIX}, page size={page_size}",
            total=total_pages - 1,
        ):
            r = client.get(
                HTTPX_URL(BASE_URL),
                cookies=cookies,
                params={"page": page, "size": page_size},
            )
            r.raise_for_status()
            res_json = r.json()
            cache.append(res_json)

        # Save cache
        with RAW_CACHE.open("w") as file:
            json.dump(cache, file)
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
