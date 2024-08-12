# -*- coding: utf-8 -*-

"""Utilities for high-level API."""

import json
from typing import Optional

import bioversions

from ..constants import VERSION_PINS
from ..utils.path import prefix_directory_join

__all__ = [
    "get_version",
    "VersionError",
]


class VersionError(ValueError):
    """A catch-all for version getting failure."""


def get_version(prefix: str) -> Optional[str]:
    """Get the version for the resource, if available.

    :param prefix: the resource name
    :return: The version if available else None
    """
    # Prioritize loaded environmental variable VERSION_PINS dictionary
    version = VERSION_PINS.get(prefix)
    if version:
        return version
    try:
        version = bioversions.get_version(prefix)
    except KeyError:
        pass  # this prefix isn't available from bioversions
    except Exception as e:
        raise ValueError(f"[{prefix}] could not get version from bioversions") from e
    else:
        if version:
            return version

    metadata_json_path = prefix_directory_join(prefix, name="metadata.json", ensure_exists=False)
    if metadata_json_path.exists():
        data = json.loads(metadata_json_path.read_text())
        return data["version"]

    return None
