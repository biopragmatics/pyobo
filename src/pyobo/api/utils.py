# -*- coding: utf-8 -*-

"""Utilities for high-level API."""

from typing import Optional

from ..sources import has_nomenclature_plugin, run_nomenclature_plugin


def get_version(prefix: str) -> Optional[str]:
    """Get the version for the resource, if available.

    :param prefix: the resource name
    :return: The version if available else None
    """
    if has_nomenclature_plugin(prefix):
        return run_nomenclature_plugin(prefix).data_version
