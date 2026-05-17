"""Get ICONCLASS as OBO."""

from collections.abc import Iterable
from urllib.parse import quote

import pandas as pd

from pyobo.struct import Obo, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "IconclassGetter",
]

PREFIX = "iconclass"
BASE_URL = "https://github.com/iconclass/data/raw/refs/heads/main/txt/en/txt_en_{}.txt"
URLS = [
    BASE_URL.format("0_1"),
    BASE_URL.format("2_3"),
    BASE_URL.format("4"),
    BASE_URL.format("5_6_7_8"),
    BASE_URL.format("9"),
    BASE_URL.format("keys"),
    # shakespeare
]


def get_df() -> pd.DataFrame:
    """Get an ICONCLASS terms dataframe."""
    df = pd.concat(
        ensure_df(prefix=PREFIX, url=url, sep="|", names=["luid", "name"]) for url in URLS
    )
    return df


def iter_terms() -> Iterable[Term]:
    """Iterate over terms in ICONCLASS."""
    for luid, name in get_df().values:
        yv = Term.from_triple(prefix=PREFIX, identifier=quote(luid), name=name)
        yield yv


class IconclassGetter(Obo):
    """An ontology representation of ICONCLASS."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


if __name__ == "__main__":
    IconclassGetter.cli()
