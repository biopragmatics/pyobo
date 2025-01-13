"""Resources from ICD."""

from .icd10 import ICD10Getter
from .icd11 import ICD11Getter

__all__ = [
    "ICD10Getter",
    "ICD11Getter",
]
