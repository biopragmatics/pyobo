"""Utilities for high-level API."""

import json
import logging
import os
from functools import lru_cache
from typing import Optional

import bioversions

from ..utils.path import prefix_directory_join

__all__ = [
    "safe_get_version",
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
    # Prioritize loaded environment variable PYOBO_VERSION_PINS dictionary
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


def safe_get_version(prefix: str) -> str:
    """Get the version."""
    v = get_version(prefix)
    if v is None:
        raise ValueError
    return v


@lru_cache(1)
def get_version_pins() -> dict[str, str]:
    """Retrieve user-defined resource version pins.

    To set your own resource pins, set your machine's environmental variable
    "PYOBO_VERSION_PINS" to a JSON string containing string resource prefixes
    as keys and string versions of their respective resource as values.
    Constraining version pins will make PyOBO rely on cached versions of a resource.
    A user might want to pin resource versions that are used by PyOBO due to
    the fact that PyOBO will download the latest version of a resource if it is
    not pinned. This downloading process can lead to a slow-down in downstream
    applications that rely on PyOBO.
    """
    version_pins_str = os.getenv("PYOBO_VERSION_PINS")
    if not version_pins_str:
        return {}

    try:
        version_pins = json.loads(version_pins_str)
    except ValueError as e:
        logger.error(
            "The value for the environment variable PYOBO_VERSION_PINS "
            "must be a valid JSON string: %s",
            e,
        )
        return {}

    for prefix, version in list(version_pins.items()):
        if not isinstance(prefix, str) or not isinstance(version, str):
            logger.error(f"The prefix:{prefix} and version:{version} name must both be strings")
            del version_pins[prefix]

    logger.debug(
        f"These are the resource versions that are pinned.\n"
        f"{version_pins}. "
        f"\nPyobo will download the latest version of a resource if it's "
        f"not pinned.\nIf you want to use a specific version of a "
        f"resource, edit your PYOBO_VERSION_PINS environmental "
        f"variable which is a JSON string to include a prefix and version "
        f"name."
    )
    return version_pins
