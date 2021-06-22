# -*- coding: utf-8 -*-

"""Converter for GWAS Central."""

import logging
import tarfile
from typing import Iterable
from xml.etree import ElementTree

from pyobo.struct import Obo, Reference, Term, has_part
from pyobo.utils.path import ensure_path

logger = logging.getLogger(__name__)

VERSION = "jan2021"
URL = f"http://www.gwascentral.org/docs/GC_{VERSION}.tar.gz"
PREFIX = "gwascentral.study"


def get_obo():
    """Get GWAS Central Studies as OBO."""
    return Obo(
        ontology=PREFIX,
        name="GWAS Central Study",
        iter_terms=iterate_terms,
        iter_terms_kwargs=dict(version=VERSION),
        data_version=VERSION,
        typedefs=[has_part],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def _get_term_from_tree(tree: ElementTree.ElementTree) -> Term:
    name = tree.find("name").text
    description = tree.find("description").text
    if description:
        description = description.strip().replace("\n", " ")
    identifier = tree.find("identifier").text
    term = Term(
        reference=Reference(PREFIX, identifier, name),
        definition=description,
    )
    for experiment in tree.findall("experiments"):
        experiment_name = experiment.find("name").text
        experiment_id = experiment.find("identifier").text
        term.append_relationship(
            has_part,
            Reference(
                "gwascentral.experiment",
                identifier=experiment_id,
                name=experiment_name,
            ),
        )
    return term


def iterate_terms(version: str) -> Iterable[Term]:
    """Iterate over GWAS Central Study terms."""
    path = ensure_path(PREFIX, url=URL, version=version)
    with tarfile.open(path) as tar_file:
        for tar_info in tar_file:
            if not tar_info.path.endswith(".xml"):
                continue
            with tar_file.extractfile(tar_info) as file:
                try:
                    tree = ElementTree.parse(file)
                except ElementTree.ParseError:
                    logger.warning("malformed XML in %s", tar_info.path)
                    continue
            yield _get_term_from_tree(tree)


if __name__ == "__main__":
    get_obo().write_default()
