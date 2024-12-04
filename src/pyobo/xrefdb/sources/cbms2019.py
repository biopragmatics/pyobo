"""Cross references from cbms2019.

.. seealso:: https://github.com/pantapps/cbms2019
"""

import pandas as pd

from pyobo.constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)

__all__ = [
    "get_cbms2019_xrefs_df",
]

#: Columns: DOID, DO name, xref xb, xref ix
base_url = "https://raw.githubusercontent.com/pantapps/cbms2019/master"
doid_to_all = f"{base_url}/mesh_icd10cm_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
all_to_all = f"{base_url}/mesh_icd10cm_via_snomedct_not_mapped_umls.tsv"
#: Columns: DOID, DO name, xref xb, xref ix
doid_to_all_2 = f"{base_url}/mesh_snomedct_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
all_to_all_2 = f"{base_url}/mesh_snomedct_via_icd10cm_not_mapped_umls.tsv"

NSM = {
    "MESH": "mesh",
    "ICD10CM": "icd",
    "SNOMEDCT_US_2016_03_01": "snomedct",
}


def _get_doid(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, sep="\t", usecols=["DO_ID", "resource", "resource_ID"])
    df.columns = [SOURCE_ID, TARGET_PREFIX, TARGET_ID]

    df[SOURCE_PREFIX] = "doid"
    df[SOURCE_ID] = df[SOURCE_ID].map(lambda s: s[len("DOID:") :])
    df[PROVENANCE] = url
    df[TARGET_PREFIX] = df[TARGET_PREFIX].map(NSM.get)
    df = df[XREF_COLUMNS]
    return df


def _get_mesh_to_icd_via_doid() -> pd.DataFrame:
    return _get_doid(doid_to_all)


def _get_mesh_to_icd_via_snomedct() -> pd.DataFrame:
    df = pd.read_csv(all_to_all, sep="\t", usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"])
    rows = []
    for snomedct_id, icd_id, mesh_id in df.values:
        rows.append(("mesh", mesh_id, "snomedct", snomedct_id, all_to_all))
        rows.append(("snomedct", snomedct_id, "icd", icd_id, all_to_all))
    return pd.DataFrame(rows, columns=XREF_COLUMNS)


def _get_mesh_to_snomedct_via_doid() -> pd.DataFrame:
    return _get_doid(doid_to_all_2)


def _get_mesh_to_snomedct_via_icd() -> pd.DataFrame:
    df = pd.read_csv(
        all_to_all_2,
        sep="\t",
        usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"],
        dtype={"SNOMEDCT_ID": float},
    )
    rows = []
    for snomedct_id, icd_id, mesh_id in df.values:
        snomedct_id = str(int(snomedct_id))
        rows.append(("mesh", mesh_id, "icd", icd_id, all_to_all))
        rows.append(("icd", icd_id, "snomedct", snomedct_id, all_to_all))
    return pd.DataFrame(rows, columns=XREF_COLUMNS)


def get_cbms2019_xrefs_df() -> pd.DataFrame:
    """Get all CBMS2019 xrefs."""
    return pd.concat(
        [
            _get_mesh_to_icd_via_doid(),
            _get_mesh_to_icd_via_snomedct(),
            _get_mesh_to_snomedct_via_doid(),
            _get_mesh_to_snomedct_via_icd(),
        ]
    ).drop_duplicates()
