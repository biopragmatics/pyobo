"""Convert NCBI Genetic Codes to an ontology.

.. seealso::

    https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes
"""

from collections.abc import Iterable

from pyobo import default_reference
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED, Obo, Reference, Term, TypeDef
from pyobo.struct.typedef import comment, has_contributor, see_also, term_replaced_by
from pyobo.utils.path import ensure_path

PREFIX = "ncbi.gc"
URI_PREFIX = (
    "https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/index.cgi?chapter=cgencodes#SG"
)
URL = "ftp://ftp.ncbi.nih.gov/entrez/misc/data/gc.prt"
VERSION = "4.6"

GC_ROOT = default_reference(prefix=PREFIX, identifier="root", name="genetic code translation table")
NCBITAXON_ROOT = Reference(prefix="NCBITaxon", identifier="1", name="root")

has_gc_code = TypeDef(
    reference=default_reference(
        prefix=PREFIX,
        identifier="hasGeneticCodeTranslationTable",
        name="has genetic code translation table",
    ),
    definition="Connects a taxonomy term to a genetic code translation table",
    domain=NCBITAXON_ROOT,
    range=GC_ROOT,
).append_contributor(CHARLIE_TERM)

NUCLEAR_GENETIC_CODE = default_reference(
    prefix=PREFIX, identifier="nuclear-genetic-code", name="nuclear genetic code translation table"
)
MITOCHONDRIAL_GENETIC_CODE = default_reference(
    prefix=PREFIX,
    identifier="mitochondrial-genetic-code",
    name="mitochondrial genetic code translation table",
)
PLASTID_GENETIC_CODE = default_reference(
    prefix=PREFIX, identifier="plastid-genetic-code", name="plastid genetic code translation table"
)
NUCLEUS = Reference(prefix="GO", identifier="0005634", name="nucleus")
MITOCHONDIA = Reference(prefix="GO", identifier="0005739", name="mitochondrion")
PLASTID = Reference(prefix="GO", identifier="0009536", name="plastid")

CATEGORY_TO_CELLULAR_COMPONENT = {
    NUCLEAR_GENETIC_CODE: NUCLEUS,
    MITOCHONDRIAL_GENETIC_CODE: MITOCHONDIA,
    PLASTID_GENETIC_CODE: PLASTID,
}
CATEGORY_TO_TABLES = {
    NUCLEAR_GENETIC_CODE: [12, 31, 6, 28, 10, 27, 29, 26, 30, 15],
    MITOCHONDRIAL_GENETIC_CODE: [14, 13, 16, 9, 5, 4, 22, 23, 21, 2, 3, 24],
    PLASTID_GENETIC_CODE: [11, 32],
}
TABLE_TO_CATEGORY = {
    str(value): key for key, values in CATEGORY_TO_TABLES.items() for value in values
}


class NCBIGCGetter(Obo):
    """Get terms in GC."""

    ontology = PREFIX
    static_version = VERSION
    root_terms = [GC_ROOT]
    typedefs = [has_gc_code, has_contributor, see_also, comment, term_replaced_by]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Get terms for GC."""
    yield CHARLIE_TERM
    yield Term(reference=NCBITAXON_ROOT)
    yield HUMAN_TERM

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

    yield (
        Term(
            reference=GC_ROOT,
            definition="A table for translating codons into amino acids. This can change for "
            "different taxa, or be different in different organelles that include genetic information.",
        )
        .append_contributor(CHARLIE_TERM)
        .append_comment(PYOBO_INJECTED)
    )

    for reference in CATEGORY_TO_TABLES:
        term = Term(reference=reference)
        term.append_parent(GC_ROOT)
        term.append_contributor(CHARLIE_TERM)
        term.append_comment(PYOBO_INJECTED)
        if substructure := CATEGORY_TO_CELLULAR_COMPONENT.get(reference):
            term.append_see_also(substructure)
        yield term

    for entry in entries:
        identifier = entry["identifier"]
        term = Term.from_triple(PREFIX, identifier, entry["name"])
        term.append_parent(TABLE_TO_CATEGORY.get(identifier, GC_ROOT))
        # TODO if symbol is available, what does it mean?
        yield term

    yield (
        Term(
            reference=Reference(prefix=PREFIX, identifier="7"),
            is_obsolete=True,
        )
        .append_replaced_by(Reference(prefix=PREFIX, identifier="4"))
        .append_comment("Kinetoplast code now merged in code id 4, as of 1995.")
    )
    yield (
        Term(
            reference=Reference(prefix=PREFIX, identifier="8"),
            is_obsolete=True,
        )
        .append_replaced_by(Reference(prefix=PREFIX, identifier="1"))
        .append_comment("all plant chloroplast differences due to RNA edit, as of 1995.")
    )

    for cellular_component in CATEGORY_TO_CELLULAR_COMPONENT.values():
        yield Term(reference=cellular_component)


if __name__ == "__main__":
    NCBIGCGetter.cli()
