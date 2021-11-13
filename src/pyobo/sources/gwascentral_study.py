# -*- coding: utf-8 -*-

"""Converter for GWAS Central."""

import logging
import tarfile
from typing import Iterable, Optional
from xml.etree import ElementTree

from pyobo.struct import Obo, Reference, Term, has_part
from pyobo.utils.path import ensure_path

logger = logging.getLogger(__name__)

VERSION = "jan2021"
URL = f"http://www.gwascentral.org/docs/GC_{VERSION}.tar.gz"
PREFIX = "gwascentral.study"


def get_obo(force: bool = False):
    """Get GWAS Central Studies as OBO."""
    return Obo(
        ontology=PREFIX,
        name="GWAS Central Study",
        iter_terms=iterate_terms,
        iter_terms_kwargs=dict(version=VERSION, force=force),
        data_version=VERSION,
        typedefs=[has_part],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def _find_text(element, name: str) -> Optional[str]:
    x = element.find(name)
    if x is not None:
        return x.text
    return None


def _get_term_from_tree(tree: ElementTree.ElementTree) -> Term:
    name = _find_text(tree, "name")
    description = _find_text(tree, "description")
    if description:
        description = description.strip().replace("\n", " ")
    identifier = _find_text(tree, "identifier")
    if identifier is None:
        raise ValueError
    term = Term(
        reference=Reference(PREFIX, identifier, name),
        definition=description,
    )
    for experiment in tree.findall("experiments"):
        experiment_name = _find_text(experiment, "name")
        experiment_identifier = _find_text(experiment, "identifier")
        if experiment_identifier is None:
            continue
        term.append_relationship(
            has_part,
            Reference(
                "gwascentral.experiment",
                identifier=experiment_identifier,
                name=experiment_name,
            ),
        )
    return term


def iterate_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over GWAS Central Study terms."""
    path = ensure_path(PREFIX, url=URL, version=version, force=force)
    with tarfile.open(path) as tar_file:
        for tar_info in tar_file:
            if not tar_info.path.endswith(".xml"):
                continue
            with tar_file.extractfile(tar_info) as file:  # type:ignore
                try:
                    tree = ElementTree.parse(file)
                except ElementTree.ParseError:
                    logger.warning("malformed XML in %s", tar_info.path)
                    continue
            yield _get_term_from_tree(tree)


if __name__ == "__main__":
    get_obo().cli()
