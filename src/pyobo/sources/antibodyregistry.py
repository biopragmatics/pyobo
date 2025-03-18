"""Converter for the Antibody Registry."""

import logging
from collections.abc import Iterable, Mapping

import lxml.html
import pandas as pd
import pystow
from httpx import Client, Timeout, Cookies, URL as httpx_URL

from bioregistry.utils import removeprefix
from tqdm.auto import tqdm

from curies import Prefix
from pyobo import Obo, Reference, Term
from pyobo.api.utils import get_version
from pyobo.struct.typedef import has_citation
from pyobo.utils.path import ensure_df

__all__ = [
    "AntibodyRegistryGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "antibodyregistry"
BASE_URL = "https://www.antibodyregistry.org/api/antibodies"
PAGE_SIZE = 1000


def get_chunks(*, force: bool = False, version: str | None = None) -> pd.DataFrame:
    """Get the BioGRID identifiers mapping dataframe."""
    if version is None:
        version = get_version(PREFIX)
    df = ensure_df(
        PREFIX,
        url=URL,
        name="results.csv",
        force=force,
        version=version,
        sep=",",
        chunksize=CHUNKSIZE,
        usecols=[0, 1, 2, 3, 5],
    )
    return df


class AntibodyRegistryGetter(Obo):
    """An ontology representation of the Antibody Registry."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_citation]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


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


def iter_terms(*, force: bool = False, version: str | None = None) -> Iterable[Term]:
    """Iterate over antibodies."""
    chunks = get_chunks(force=force, version=version)
    needs_curating = set()
    # df['vendor'] = df['vendor'].map(bioregistry.normalize_prefix)
    it = tqdm(chunks, desc=f"{PREFIX}, chunkssize={CHUNKSIZE}")
    for chunk in it:
        for identifier, name, vendor, catalog_number, defining_citation in chunk.values:
            if pd.isna(identifier):
                continue
            identifier = removeprefix(identifier, "AB_")
            term = Term.from_triple(PREFIX, identifier, name if pd.notna(name) else None)
            if vendor not in MAPPING:
                if vendor not in needs_curating:
                    needs_curating.add(vendor)
                    if all(x not in vendor for x in SKIP):
                        logger.debug(f"! vendor {vendor} for {identifier}")
            elif MAPPING[vendor] is not None and pd.notna(catalog_number) and catalog_number:
                term.append_xref((MAPPING[vendor], catalog_number))  # type:ignore
            if defining_citation and pd.notna(defining_citation):
                for pubmed_id in defining_citation.split(","):
                    pubmed_id = pubmed_id.strip()
                    if not pubmed_id:
                        continue
                    term.append_provenance(Reference(prefix="pubmed", identifier=pubmed_id))
            yield term


def _get_term(json_data: dict[str, None | str | list[str]]) -> Term:
    identifier = json_data["abId"]
    name = json_data["abName"]
    vendor = json_data["vendorName"]
    catalog_number = json_data["catalogNum"]
    defining_citation = json_data["definingCitation"]
    term = Term.from_triple(prefix=PREFIX, identifier=identifier, name=name)

    if vendor not in MAPPING:
        logger.debug(f"! vendor {vendor} for {identifier}")
    elif MAPPING[vendor] is not None and catalog_number:
        term.append_xref((MAPPING[vendor], catalog_number))
    if defining_citation:
        for pubmed_id in defining_citation.split(","):
            pubmed_id = pubmed_id.strip().removeprefix("PMID: ")
            if not pubmed_id:
                continue
            term.append_provenance(
                Reference(prefix=Prefix("pubmed"), identifier=pubmed_id, name=None)
            )
    return term


def get_data(max_pages: int = None, page_size: int = PAGE_SIZE) -> Iterable[Term]:
    """Get the BioGRID identifiers mapping dataframe."""
    cookies = antibodyregistry_login()
    with Client(
        http2=True,
        timeout=Timeout(5.0),
    ) as client:
        r = client.get(
            httpx_URL(BASE_URL),
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

        for item in res_json["items"]:
            # todo: makes use of more fields in the JSON? All fields:
            #  catalogNum, vendorName, clonality, epitope, comments, url, abName,
            #  abTarget, cloneId, commercialType, definingCitation, productConjugate,
            #  productForm, productIsotype, sourceOrganism, targetSpecies, uniprotId,
            #  applications, kitContents, abTargetEntrezId, abTargetUniprotId,
            #  numOfCitation, accession, status, feedback, abId, catAlt, curateTime,
            #  curatorComment, discDate, insertTime, targetModification,
            #  targetSubregion, vendorId, lastEditTime, ix, showLink, vendorUrl
            term = _get_term(item)
            yield term

        # Now, iterate over the remaining pages
        for page in tqdm(
            range(2, total_pages + 1),
            desc=f"{PREFIX}, page size={page_size}",
            total=total_pages - 1,
        ):
            r = client.get(
                httpx_URL(BASE_URL),
                cookies=cookies,
                params={"page": page, "size": page_size},
            )
            r.raise_for_status()
            res_json = r.json()
            for item in res_json["items"]:
                term = _get_term(item)
                yield term


def antibodyregistry_login() -> Cookies:
    """Login to Antibody Registry."""
    logger.info("Logging in to Antibody Registry")
    username = pystow.get_config(
        "pyobo", "antibodyregistry_username", raise_on_missing=True
    )
    password = pystow.get_config(
        "pyobo", "antibodyregistry_password", raise_on_missing=True
    )
    with Client(
        follow_redirects=True,
        http2=True,
        timeout=Timeout(5.0),
    ) as client:
        r = client.get(httpx_URL("https://www.antibodyregistry.org/login"))
        r.raise_for_status()

        cookies = r.cookies
        tree = lxml.html.fromstring(r.content)
        login_post_url = httpx_URL(tree.xpath('//form[@id="kc-form-login"]/@action')[0])

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
