"""Importers for selventa terminologies."""

from .schem import SCHEMGetter
from .scomp import SCOMPGetter
from .sdis import SDISGetter
from .sfam import SFAMGetter

__all__ = [
    "SCHEMGetter",
    "SCOMPGetter",
    "SDISGetter",
    "SFAMGetter",
]
