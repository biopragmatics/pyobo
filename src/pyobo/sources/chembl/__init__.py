"""Resources from ChEMBL."""

from .chembl_compound import ChEMBLCompoundGetter
from .chembl_target import ChEMBLTargetGetter

__all__ = [
    "ChEMBLCompoundGetter",
    "ChEMBLTargetGetter",
]
