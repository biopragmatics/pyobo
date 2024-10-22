"""Converter for GWAS Central."""

import logging
import tarfile
from collections.abc import Iterable
from typing import Optional
from xml.etree import ElementTree

from pyobo.struct import Obo, Reference, Term, has_part
from pyobo.utils.path import ensure_path

__all__ = [
    "GWASCentralStudyGetter",
]

logger = logging.getLogger(__name__)

VERSION = "jan2021"
PREFIX = "gwascentral.study"


class GWASCentralStudyGetter(Obo):
    """An ontology representation of GWAS Central's study nomenclature."""

    ontology = PREFIX
    static_version = VERSION
    typedefs = [has_part]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False):
    """Get GWAS Central Studies as OBO."""
    return GWASCentralStudyGetter(force=force)


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
        reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
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
                prefix="gwascentral.experiment",
                identifier=experiment_identifier,
                name=experiment_name,
            ),
        )
    return term


def iterate_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over GWAS Central Study terms."""
    url = f"http://www.gwascentral.org/docs/GC_{version}.tar.gz"
    path = ensure_path(PREFIX, url=url, version=version, force=force)
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
    GWASCentralStudyGetter.cli()
