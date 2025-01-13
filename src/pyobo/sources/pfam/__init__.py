"""Resources from PFAM."""

from .pfam import PfamGetter
from .pfam_clan import PfamClanGetter

__all__ = [
    "PfamClanGetter",
    "PfamGetter",
]
