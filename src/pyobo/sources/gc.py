"""Convert NCBI Genetic Codes to an ontology.

.. seealso:: https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes
"""

from collections.abc import Iterable

from pyobo.struct import Obo, Reference, Term, TypeDef, int_identifier_sort_key
from pyobo.utils.path import ensure_path

PREFIX = "gc"
URI_PREFIX = (
    "https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes#SG"
)
URL = "ftp://ftp.ncbi.nih.gov/entrez/misc/data/gc.prt"
VERSION = "4.6"

ROOT = Reference(prefix=PREFIX, identifier="0", name="genetic code")
TAX_ROOT = Reference(prefix="NCBITaxon", identifier="1", name="root")

has_gc_code = TypeDef(
    reference=Reference(prefix=PREFIX, identifier="1000000", name="has GC code"),
    definition="Connects a taxonomy term to a GC code",
    domain=TAX_ROOT,
    range=ROOT,
)


class GCGetter(Obo):
    """Get terms in GC."""

    ontology = PREFIX
    static_version = VERSION
    term_sort_key = int_identifier_sort_key
    root_terms = [ROOT]
    typedefs = [has_gc_code]
    idspaces = {PREFIX: URI_PREFIX}

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Get terms for GC."""
    path = ensure_path(PREFIX, url=URL)
    # first, remove comment lines
    lines = [
        line.strip()
        for line in path.read_text().splitlines()
        if not line.startswith("--") and line.strip()
    ]

    lines = lines[1:-2]
    entries: list[dict[str, str]] = []
    entry: dict[str, str] = {}
    for line in lines:
        # start a new entry
        if line == "{":
            if entry:
                entries.append(entry)
            entry = {}
        elif line == "},":
            pass
        else:
            key, data = line.split(" ", 1)
            if key == "name":
                data = data.lstrip('"')
                if data.startswith("SGC"):
                    key = "symbol"
                entry[key] = data.rstrip(",").rstrip().rstrip('"')
            elif key == "id":
                entry["identifier"] = data.rstrip(",").rstrip()

    terms = [Term(reference=ROOT)]
    for entry in entries:
        term = Term.from_triple(PREFIX, entry["identifier"], entry["name"])
        term.append_parent(ROOT)
        # TODO if symbol is available, what does it mean?
        terms.append(term)

    return terms


if __name__ == "__main__":
    GCGetter().write_default(write_obo=True, write_owl=True, force=True)
