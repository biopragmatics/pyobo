"""Convert NCBI Genetic Codes to an ontology.

.. seealso:: https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes
"""

from collections.abc import Iterable

from pyobo.struct import Obo, Reference, Term, TypeDef, int_identifier_sort_key
from pyobo.struct.typedef import contributor
from pyobo.utils.path import ensure_path

PREFIX = "gc"
URI_PREFIX = (
    "https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes#SG"
)
URL = "ftp://ftp.ncbi.nih.gov/entrez/misc/data/gc.prt"
VERSION = "4.6"

GC_ROOT = Reference(prefix=PREFIX, identifier="0", name="genetic code")
NCBITAXON_ROOT = Reference(prefix="NCBITaxon", identifier="1", name="root")

has_gc_code = TypeDef(
    reference=Reference(prefix=PREFIX, identifier="1000000", name="has GC code"),
    definition="Connects a taxonomy term to a GC code",
    domain=NCBITAXON_ROOT,
    range=GC_ROOT,
)
CHARLIE = Reference(prefix="orcid", identifier="0000-0003-4423-4370", name="Charles Tapley Hoyt")

NUCLEAR_GENETIC_CODE = Reference(prefix=PREFIX, identifier="2000001", name="nuclear genetic code")
MITOCHONDRIAL_GENETIC_CODE = Reference(
    prefix=PREFIX, identifier="2000002", name="mitochondrial genetic code"
)
PLASTID_GENETIC_CODE = Reference(prefix=PREFIX, identifier="2000003", name="plastid genetic code")
MACRONUCLEAR_GENETIC_CODE = Reference(
    prefix=PREFIX, identifier="2000004", name="macronuclear genetic code"
)

CHILDREN = {
    NUCLEAR_GENETIC_CODE: [12, 31, 6, 28, 10, 27, 29, 26, 30],
    MITOCHONDRIAL_GENETIC_CODE: [14, 13, 16, 9, 5, 4, 22, 23, 21, 2, 3, 24],
    PLASTID_GENETIC_CODE: [11, 32],
    MACRONUCLEAR_GENETIC_CODE: [15],
}
XY = {str(value): key for key, values in CHILDREN.items() for value in values}


class GCGetter(Obo):
    """Get terms in GC."""

    ontology = PREFIX
    static_version = VERSION
    term_sort_key = int_identifier_sort_key
    root_terms = [GC_ROOT]
    typedefs = [has_gc_code]
    idspaces = {
        PREFIX: URI_PREFIX,
        "orcid": "https://orcid.org/",
        "dcterms": "http://purl.org/dc/terms/",
    }

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

    terms = [
        Term(reference=GC_ROOT),
        Term(reference=NCBITAXON_ROOT),
    ]
    for reference in CHILDREN:
        term = Term(reference=reference)
        term.append_parent(GC_ROOT)
        term.annotate_object(contributor, CHARLIE)
        terms.append(term)

    for entry in entries:
        identifier = entry["identifier"]
        term = Term.from_triple(PREFIX, identifier, entry["name"])
        term.append_parent(XY.get(identifier, GC_ROOT))
        # TODO if symbol is available, what does it mean?
        terms.append(term)

    terms.append(
        Term(
            reference=Reference(prefix=PREFIX, identifier="7"),
            is_obsolete=True,
        )
        .append_replaced_by(Reference(prefix=PREFIX, identifier="4"))
        .append_comment("Kinetoplast code now merged in code id 4, as of 1995.")
    )
    terms.append(
        Term(
            reference=Reference(prefix=PREFIX, identifier="8"),
            is_obsolete=True,
        )
        .append_replaced_by(Reference(prefix=PREFIX, identifier="1"))
        .append_comment("all plant chloroplast differences due to RNA edit, as of 1995.")
    )

    return terms


if __name__ == "__main__":
    GCGetter().write_default(write_obo=True, write_owl=True, force=True)
