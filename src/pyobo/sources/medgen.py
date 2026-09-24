"""A source for MedGen.

.. seealso:: motivated by improving https://github.com/monarch-initiative/medgen
"""

from collections.abc import Iterable

from pyobo import Obo, Term

__all__ = ["MedGenGetter"]

PREFIX = "medgen"
VERSION_URL = "https://ftp.ensembl.org/pub/VERSION"

"""

See https://ftp.ncbi.nlm.nih.gov/pub/medgen/

Parent Directory                                    -
csv/                           2026-09-20 22:18    -
presentations/                 2025-04-11 10:13    -
HPO_CUI_history.txt            2026-09-20 22:18  1.3M
MERGED.RRF.gz                  2026-09-20 22:15   49K
MGCONSO.RRF.gz                 2026-09-20 22:15   15M
MGDEF.RRF.gz                   2026-09-20 22:16  5.1M
MGREL.RRF.gz                   2026-09-20 22:16   15M
MGSAT.RRF.gz                   2026-09-20 22:16   11M
MGSTY.RRF.gz                   2026-09-20 22:16  1.6M
MONDO_CUI_history.txt          2026-09-20 22:18  1.0M
MedGenIDMappings.txt.gz        2026-09-20 22:16  5.5M
MedGen_CUI_history.txt         2026-09-20 22:18   89K
MedGen_HPO_Mapping.txt.gz      2026-09-20 22:16  389K
MedGen_HPO_OMIM_Mapping.txt.gz 2026-09-20 22:16  4.1M
MedGen_Sources.txt             2026-09-20 22:18   10K
MedGen_UID_CUI_history.txt     2026-09-20 22:18   57M
NAMES.RRF.gz                   2026-09-20 22:15  3.0M
ORDO_CUI_history.txt           2026-09-20 22:18  1.1M
README.txt                     2024-11-08 09:38   17K
medgen_pubmed_lnk.txt.gz       2026-09-20 22:17   82M

"""


class MedGenGetter(Obo):
    """An ontology representation of the Ensembl database."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in the ontology."""
    raise NotImplementedError
