"""Unimod provides an OBO file, but it's got lots of errors in its encoding."""

from collections.abc import Iterable

from lxml import etree

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

URL = "https://www.unimod.org/xml/unimod.xml"
PREFIX_MAP = {"umod": "http://www.unimod.org/xmlns/schema/unimod_2"}
PREFIX = "unimod"


class UnimodGetter(Obo):
    """An ontology representation of the unimod modifications."""

    ontology = bioversions_key = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Get terms."""
    path = ensure_path("unimod", url=URL)
    x = etree.parse(path).getroot()
    mods = x.findall("umod:modifications/umod:mod", namespaces=PREFIX_MAP)
    return map(_mod_to_term, mods)


def _mod_to_term(mod: etree.Element) -> Term:
    title = mod.attrib["title"]
    name = mod.attrib["full_name"]
    identifier = mod.attrib["record_id"]
    term = Term(
        reference=Reference(prefix=PREFIX, identifier=identifier, name=title),
        definition=name if name != title else None,
    )
    return term


if __name__ == "__main__":
    UnimodGetter.cli()
