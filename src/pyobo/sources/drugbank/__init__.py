"""Resources from DrugBank."""

from .drugbank import DrugBankGetter
from .drugbank_salt import DrugBankSaltGetter

__all__ = [
    "DrugBankGetter",
    "DrugBankSaltGetter",
]
