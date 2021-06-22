# -*- coding: utf-8 -*-

"""Utilities for converters."""

import logging
from typing import Mapping, Set, Tuple

from ..utils.io import multisetdict

__all__ = [
    "get_go_mapping",
    "process_go_mapping_line",
]

logger = logging.getLogger(__name__)


def get_go_mapping(path: str, prefix: str) -> Mapping[str, Set[Tuple[str, str]]]:
    """Get a GO mapping file."""
    with open(path) as file:
        return multisetdict(
            process_go_mapping_line(line.strip(), prefix=prefix) for line in file if line[0] != "!"
        )


def process_go_mapping_line(line: str, prefix: str) -> Tuple[str, Tuple[str, str]]:
    """Process a GO mapping line."""
    line1 = line[len(f"{prefix}:") :]
    line2, go_id = line1.rsplit(";", 1)
    go_id = go_id.strip()[len("GO:") :]
    try:
        line3, go_name = line2.rsplit(">", 1)
    except ValueError:
        logger.warning(line)
        logger.warning("go:%s", go_id)
        raise

    go_name = go_name.strip()[len("GO:") :]
    interpro_id, _interpro_name = line3.split(" ", 1)
    interpro_id = interpro_id.strip()
    return interpro_id, (go_id, go_name)
