"""Resources from HGNC."""

from .hgnc import HGNCGetter
from .hgncgenefamily import HGNCGroupGetter

__all__ = [
    "HGNCGetter",
    "HGNCGroupGetter",
]
