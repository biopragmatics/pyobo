"""Resources from GWAS Central."""

from .gwascentral_phenotype import GWASCentralPhenotypeGetter
from .gwascentral_study import GWASCentralStudyGetter

__all__ = [
    "GWASCentralPhenotypeGetter",
    "GWASCentralStudyGetter",
]
