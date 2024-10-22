"""Import ComPath mappings between pathways."""

from collections.abc import Iterable

import pandas as pd
from pystow.utils import get_commit

from pyobo.constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)

__all__ = [
    "iter_compath_dfs",
]


def _get_df(name: str, *, sha: str, sep: str = ",") -> pd.DataFrame:
    url = f"https://raw.githubusercontent.com/ComPath/compath-resources/{sha}/mappings/{name}"
    df = pd.read_csv(
        url,
        sep=sep,
        usecols=["Source Resource", "Source ID", "Mapping Type", "Target Resource", "Target ID"],
    )
    df.rename(
        columns={
            "Source Resource": SOURCE_PREFIX,
            "Source ID": SOURCE_ID,
            "Target Resource": TARGET_PREFIX,
            "Target ID": TARGET_ID,
        },
        inplace=True,
    )
    df = df[df["Mapping Type"] == "equivalentTo"]
    del df["Mapping Type"]
    df[PROVENANCE] = url
    df = df[XREF_COLUMNS]

    df[SOURCE_PREFIX] = df[SOURCE_PREFIX].map(_fix_kegg_prefix)
    df[TARGET_PREFIX] = df[TARGET_PREFIX].map(_fix_kegg_prefix)
    df[SOURCE_ID] = [
        _fix_kegg_identifier(prefix, identifier)
        for prefix, identifier in df[[SOURCE_PREFIX, SOURCE_ID]].values
    ]
    df[TARGET_ID] = [
        _fix_kegg_identifier(prefix, identifier)
        for prefix, identifier in df[[TARGET_PREFIX, TARGET_ID]].values
    ]

    return df


def _fix_kegg_identifier(prefix, identifier) -> str:
    if prefix == "kegg.pathway":
        return identifier[len("path:") :]
    return identifier


def _fix_kegg_prefix(s):
    return s if s != "kegg" else "kegg.pathway"


def iter_compath_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over all ComPath mappings."""
    sha = get_commit("ComPath", "compath-resources")

    yield _get_df("kegg_reactome.csv", sha=sha)
    yield _get_df("kegg_wikipathways.csv", sha=sha)
    yield _get_df("pathbank_kegg.csv", sha=sha)
    yield _get_df("pathbank_reactome.csv", sha=sha)
    yield _get_df("pathbank_wikipathways.csv", sha=sha)
    yield _get_df("special_mappings.csv", sha=sha)
    yield _get_df("wikipathways_reactome.csv", sha=sha)


def get_compath_xrefs_df() -> pd.DataFrame:
    """Iterate over all ComPath mappings."""
    return pd.concat(iter_compath_dfs())
