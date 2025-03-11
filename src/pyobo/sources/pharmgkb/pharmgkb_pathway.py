"""An ontology representation of PharmGKB pathways."""

import zipfile
from collections.abc import Iterable

from pyobo import Obo, Term
from pyobo.sources.pharmgkb.utils import download_pharmgkb

__all__ = [
    "PharmGKBPathwayGetter",
]

PREFIX = "pharmgkb.pathways"
BIOPAX_URL = "https://api.pharmgkb.org/v1/download/file/data/pathways-biopax.zip"
EXTENSION = ".owl"


class PharmGKBPathwayGetter(Obo):
    """An ontology representation of PharmGKB pathways."""

    ontology = bioversions_key = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over terms.

    :param force: Should the data be re-downloaded

    :yields: Terms

    1. PharmGKB Accession Id = Identifier assigned to this phenotype by PharmGKB
    2. Name = Name PharmGKB uses for this phenotype
    3. Alternate Names = Other known names for this phenotype, comma-separated
    4. Cross-references = References to other resources in the form "resource:id",
       comma-separated
    5. External Vocabulary = Term for this phenotype in another vocabulary in the form
       "vocabulary:id", comma-separated
    """
    path = download_pharmgkb(PREFIX, url=BIOPAX_URL, force=force)
    with zipfile.ZipFile(path) as zf:
        for zip_info in zf.filelist:
            if not zip_info.filename.endswith(EXTENSION):
                continue
            with zf.open(zip_info) as file:
                yield _process_biopax(zip_info, file)


def _process_biopax(path: zipfile.ZipInfo, file) -> Term:
    fname = path.filename.removesuffix(EXTENSION).strip().replace("\r\n", " ")
    identifier, _, name = fname.partition("-")
    name = name.replace("_", " ")
    term = Term.from_triple(PREFIX, identifier, name)
    # TODO parse file with pybiopax to include members and provenance
    return term


if __name__ == "__main__":
    PharmGKBPathwayGetter.cli()
