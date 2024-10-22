"""Interface for caching data on AWS S3."""

import logging
import os
from typing import Optional

import boto3
import humanize
from tabulate import tabulate

from pyobo import (
    get_id_name_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_properties_df,
    get_relations_df,
    get_xrefs_df,
)
from pyobo.api.utils import get_version
from pyobo.constants import RAW_DIRECTORY
from pyobo.registries import iter_cached_obo
from pyobo.utils.path import prefix_cache_join

__all__ = [
    "download_artifacts",
    "upload_artifacts",
    "upload_artifacts_for_prefix",
    "list_artifacts",
]

logger = logging.getLogger(__name__)


def download_artifacts(bucket: str, suffix: Optional[str] = None) -> None:
    """Download compiled parts from AWS.

    :param bucket: The name of the S3 bucket to download
    :param suffix: If specified, only download files with this suffix. Might
     be useful to specify ``suffix='names.tsv`` if you just want to run the
     name resolution service.
    """
    s3_client = boto3.client("s3")
    all_objects = s3_client.list_objects(Bucket=bucket)
    for entry in all_objects["Contents"]:
        key = entry["Key"]
        if suffix and not key.endswith(suffix):
            pass
        path = os.path.join(RAW_DIRECTORY, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            continue  # no need to download again
        logging.warning("downloading %s to %s", key, path)
        s3_client.download_file(bucket, key, path)


def upload_artifacts(
    bucket: str,
    whitelist: Optional[set[str]] = None,
    blacklist: Optional[set[str]] = None,
    s3_client=None,
) -> None:
    """Upload all artifacts to AWS."""
    if s3_client is None:
        s3_client = boto3.client("s3")
    all_objects = s3_client.list_objects(Bucket=bucket)
    uploaded_prefixes = {entry["Key"].split("/")[0] for entry in all_objects["Contents"]}

    for prefix, _ in sorted(iter_cached_obo()):
        if prefix in uploaded_prefixes:
            continue
        if whitelist and prefix not in whitelist:
            continue
        if blacklist and prefix in blacklist:
            continue
        upload_artifacts_for_prefix(prefix=prefix, bucket=bucket, s3_client=s3_client)


def upload_artifacts_for_prefix(
    *, prefix: str, bucket: str, s3_client=None, version: Optional[str] = None
):
    """Upload compiled parts for the given prefix to AWS."""
    if s3_client is None:
        s3_client = boto3.client("s3")

    if version is None:
        version = get_version(prefix)

    logger.info("[%s] getting id->name mapping", prefix)
    get_id_name_mapping(prefix)
    id_name_path = prefix_cache_join(prefix, name="names.tsv", version=version)
    if not id_name_path.exists():
        raise FileNotFoundError
    id_name_key = os.path.join(prefix, "cache", "names.tsv")
    logger.info("[%s] uploading id->name mapping", prefix)
    upload_file(path=id_name_path, bucket=bucket, key=id_name_key, s3_client=s3_client)

    logger.info("[%s] getting id->synonyms mapping", prefix)
    get_id_synonyms_mapping(prefix)
    id_synonyms_path = prefix_cache_join(prefix, name="synonyms.tsv", version=version)
    if not id_synonyms_path.exists():
        raise FileNotFoundError
    id_synonyms_key = os.path.join(prefix, "cache", "synonyms.tsv")
    logger.info("[%s] uploading id->synonyms mapping", prefix)
    upload_file(path=id_synonyms_path, bucket=bucket, key=id_synonyms_key, s3_client=s3_client)

    logger.info("[%s] getting xrefs", prefix)
    get_xrefs_df(prefix)
    xrefs_path = prefix_cache_join(prefix, name="xrefs.tsv", version=version)
    if not xrefs_path.exists():
        raise FileNotFoundError
    xrefs_key = os.path.join(prefix, "cache", "xrefs.tsv")
    logger.info("[%s] uploading xrefs", prefix)
    upload_file(path=xrefs_path, bucket=bucket, key=xrefs_key, s3_client=s3_client)

    logger.info("[%s] getting relations", prefix)
    get_relations_df(prefix)
    relations_path = prefix_cache_join(prefix, name="relations.tsv", version=version)
    if not relations_path.exists():
        raise FileNotFoundError
    relations_key = os.path.join(prefix, "cache", "relations.tsv")
    logger.info("[%s] uploading relations", prefix)
    upload_file(path=relations_path, bucket=bucket, key=relations_key, s3_client=s3_client)

    logger.info("[%s] getting properties", prefix)
    get_properties_df(prefix)
    properties_path = prefix_cache_join(prefix, name="properties.tsv", version=version)
    if not properties_path.exists():
        raise FileNotFoundError
    properties_key = os.path.join(prefix, "cache", "properties.tsv")
    logger.info("[%s] uploading properties", prefix)
    upload_file(path=properties_path, bucket=bucket, key=properties_key, s3_client=s3_client)

    logger.info("[%s] getting alternative identifiers", prefix)
    get_id_to_alts(prefix)
    alts_path = prefix_cache_join(prefix, name="alt_ids.tsv", version=version)
    if not alts_path.exists():
        raise FileNotFoundError
    alts_key = os.path.join(prefix, "cache", "alt_ids.tsv")
    logger.info("[%s] uploading alternative identifiers", prefix)
    upload_file(path=alts_path, bucket=bucket, key=alts_key)


def upload_file(*, path, bucket, key, s3_client=None):
    """Upload a file to an S3 bucket.

    :param path: The local file path
    :param bucket: The name of the S3 bucket
    :param key: The relative file path to put on the S3 bucket
    """
    if s3_client is None:
        s3_client = boto3.client("s3")
    s3_client.upload_file(path, bucket, key)


def list_artifacts(bucket: str) -> str:
    """List the files in a given bucket."""
    s3_client = boto3.client("s3")
    all_objects = s3_client.list_objects(Bucket=bucket)
    rows = [
        (entry["Key"], humanize.naturalsize(entry["Size"])) for entry in all_objects["Contents"]
    ]
    return tabulate(rows, headers=["File", "Size"])
