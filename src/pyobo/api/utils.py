# -*- coding: utf-8 -*-

"""Utilities for high-level API."""

import json
import logging
import os
from typing import Optional

import bioversions

from ..utils.path import prefix_directory_join

__all__ = [
    "get_version",
    "get_version_pins",
    "VersionError",
]

logger = logging.getLogger(__name__)


class VersionError(ValueError):
    """A catch-all for version getting failure."""


def get_version(prefix: str) -> Optional[str]:
    """Get the version for the resource, if available.

    :param prefix: the resource name
    :return: The version if available else None
    """
    # Prioritize loaded environmental variable VERSION_PINS dictionary
    version = get_version_pins().get(prefix)
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


def get_version_pins():
    """Retrieve the resource version pins."""
    try:
        version_pins_str = os.getenv("VERSION_PINS")
        if not version_pins_str:
            version_pins = {}
        else:
            version_pins = json.loads(version_pins_str)
            invalid_prefixes = []
            for prefix, version in version_pins.items():
                if not isinstance(prefix, str) or not isinstance(version, str):
                    logger.error(
                        f"The prefix:{prefix} and version:{version} name must both be strings"
                    )
                    invalid_prefixes.append(prefix)
            for prefix in invalid_prefixes:
                version_pins.pop(prefix)
    except ValueError as e:
        logger.error(
            "The value for the environment variable VERSION_PINS must be a valid JSON string: %s"
            % e
        )
        version_pins = {}

    if version_pins:
        logger.debug(
            f"These are the resource versions that are pinned.\n"
            f"{version_pins}. "
            f"\nPyobo will download the latest version of a resource if it's "
            f"not pinned.\nIf you want to use a specific version of a "
            f"resource, edit your VERSION_PINS environmental "
            f"variable which is a JSON string to include a prefix and version "
            f"name."
        )
    return version_pins
