# -*- coding: utf-8 -*-

"""Utilities for high-level API."""

import json
import logging
from typing import Optional

from ..sources import has_nomenclature_plugin, run_nomenclature_plugin
from ..utils.path import prefix_directory_join

logger = logging.getLogger(__name__)


def get_version(prefix: str) -> Optional[str]:
    """Get the version for the resource, if available.

    :param prefix: the resource name
    :return: The version if available else None
    """
    if has_nomenclature_plugin(prefix):
        return run_nomenclature_plugin(prefix).data_version

    metadata_json_path = prefix_directory_join(prefix, name="metadata.json", ensure_exists=False)
    if metadata_json_path.exists():
        with metadata_json_path.open() as file:
            data = json.load(file)
        rv = data["version"]
        logger.debug("using pre-cached metadata version %s v%s", prefix, rv)
        return rv
