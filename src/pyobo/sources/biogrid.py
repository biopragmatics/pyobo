"""Extract and convert BioGRID identifiers."""

from collections.abc import Mapping
from functools import partial

import pandas as pd

from pyobo.api.utils import get_version
from pyobo.resources.ncbitaxon import get_ncbitaxon_id
from pyobo.utils.cache import cached_mapping
from pyobo.utils.path import ensure_df, prefix_directory_join

PREFIX = "biogrid"
BASE_URL = "https://downloads.thebiogrid.org/Download/BioGRID/Release-Archive"

taxonomy_remapping = {  # so much for official names
    "Canis familiaris": "9615",  # Canis lupus familiaris
    "Human Herpesvirus 1": "10298",  # Human alphaherpesvirus 1
    "Human Herpesvirus 3": "10335",  # Human alphaherpesvirus 3
    "Murid Herpesvirus 1": "10366",  # Murid betaherpesvirus 1
    "Human Herpesvirus 4": "10376",  # Human gammaherpesvirus 4
    "Hepatitus C Virus": "11103",  # Hepacivirus C
    "Human Immunodeficiency Virus 1": "11676",  # Human immunodeficiency virus 1
    "Human Immunodeficiency Virus 2": "11709",  # Human immunodeficiency virus 2
    "Human Herpesvirus 2": "10310",  # Human alphaherpesvirus 2
    "Human Herpesvirus 5": "10359",  # Human betaherpesvirus 5
    "Human Herpesvirus 6A": "32603",  # Human betaherpesvirus 6A
    "Human Herpesvirus 6B": "32604",  # Human betaherpesvirus 6B
    "Human Herpesvirus 7": "10372",  # Human betaherpesvirus 7
    "Human Herpesvirus 8": "37296",  # Human gammaherpesvirus 8
    "Emericella nidulans": "162425",  # Aspergillus nidulans
    "Bassica campestris": "145471",  # Brassica rapa subsp. oleifera (was a typo)
    "Tarsius syrichta": "1868482",  # Carlito syrichta
    "Felis Catus": "9685",  # Felis catus
    "Vaccinia Virus": "10245",  # Vaccinia virus
    "Simian Virus 40": "1891767",  # Macaca mulatta polyomavirus 1
    "Simian Immunodeficiency Virus": "11723",  # Simian immunodeficiency virus
    "Tobacco Mosaic Virus": "12242",  # Tobacco mosaic virus
    # Not in my current dump, but definitely there!
    "Severe acute respiratory syndrome coronavirus 2": "2697049",  # Severe acute respiratory syndrome coronavirus 2
    "Middle-East Respiratory Syndrome-related Coronavirus": "1335626",
}


def _lookup(name: str) -> str | None:
    if name in taxonomy_remapping:
        return taxonomy_remapping[name]
    return get_ncbitaxon_id(name)


def get_df() -> pd.DataFrame:
    """Get the BioGRID identifiers mapping dataframe."""
    version = get_version("biogrid")
    url = f"{BASE_URL}/BIOGRID-{version}/BIOGRID-IDENTIFIERS-{version}.tab.zip"
    df = ensure_df(PREFIX, url=url, skiprows=28, dtype=str, version=version)
    df["taxonomy_id"] = df["ORGANISM_OFFICIAL_NAME"].map(_lookup)
    return df


@cached_mapping(
    path=prefix_directory_join(
        PREFIX,
        "cache",
        "xrefs",
        name="ncbigene.tsv",
        version=partial(get_version, PREFIX),
    ),
    header=["biogrid_id", "ncbigene_id"],
)
def get_ncbigene_mapping() -> Mapping[str, str]:
    """Get BioGRID to NCBIGene mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs

        biogrid_ncbigene_mapping = get_filtered_xrefs("biogrid", "ncbigene")
    """
    df = get_df()
    df = df.loc[df["IDENTIFIER_TYPE"] == "ENTREZ_GENE", ["BIOGRID_ID", "IDENTIFIER_VALUE"]]
    return dict(df.values)
