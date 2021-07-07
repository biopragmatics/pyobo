# -*- coding: utf-8 -*-

"""DepMap cell lines."""

from typing import Iterable, Optional

import click
import pandas as pd
import pystow
from more_click import verbose_option

from pyobo import Obo, Reference, Term

__all__ = [
    "get_obo",
]

PREFIX = "depmap"


def get_obo(*, version: Optional[str] = None, force: bool = False) -> Obo:
    """Get DepMap cell lines as OBO."""
    if version is None:
        version = get_version()
    return Obo(
        ontology=PREFIX,
        name="DepMap Cell Lines",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version, force=force),
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_version() -> str:
    """Get the latest version of the DepMap cell line metadata."""
    return "21Q2"


def get_url(version: Optional[str] = None) -> str:
    """Get the URL for the given version of the DepMap cell line metadata file.

    :param version: The version of the data
    :returns: The URL as a string for downloading the dat

    .. warning::

        This does not currently take the version into account. Need to write a crawler since data is not easy
        to access.
    """
    #: This is the DepMap Public 21Q2 version. There isn't a way to do this automatically without writing a crawler
    url = "https://ndownloader.figshare.com/files/27902376"
    return url


def _fix_mangled_int(x: str) -> str:
    return str(int(float(x))) if pd.notna(x) else None


def iter_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Iterate over DepMap cell line terms."""
    df = ensure(force=force, version=version)
    columns = [
        "DepMap_ID",
        "cell_line_name",
        "stripped_cell_line_name",
        "alias",
        "COSMICID",
        "RRID",
        "WTSI_Master_Cell_ID",
        "Sanger_Model_ID",
    ]
    df["WTSI_Master_Cell_ID"] = df["WTSI_Master_Cell_ID"].map(_fix_mangled_int)
    df["COSMICID"] = df["COSMICID"].map(_fix_mangled_int)
    for identifier, name, sname, aliases, cosmic_id, cellosaurus_id, _wtsi_id, _sanger_id in df[
        columns
    ].values:
        term = Term.from_triple(PREFIX, identifier, name)
        if pd.notna(sname):
            term.append_synonym(sname)
        if pd.notna(aliases):
            for alias in aliases.split(","):
                alias = alias.strip()
                if alias == name:
                    continue
                term.append_synonym(alias)
        if pd.notna(cosmic_id):
            term.append_xref(Reference("cosmic.cell", cosmic_id))
        if pd.notna(cellosaurus_id):
            term.append_xref(Reference("cellosaurus", cellosaurus_id))

        # WTSI stands for welcome trust sanger institute
        # Not sure where this prefix goes
        # if pd.notna(wtsi_id):
        #    term.append_xref(Reference("sanger", wtsi_id))

        # Not sure what this is
        # if pd.notna(sanger_id):
        #    term.append_xref(Reference("sanger", sanger_id))

        # TODO There's lots of other great ontological information in here. Next time.
        yield term


def ensure(version: Optional[str] = None, force: bool = False) -> pd.DataFrame:
    """Ensure and parse the given version of the DepMap cell line metadata."""
    if version is None:
        version = get_version()

    return pystow.ensure_csv(
        "pyobo",
        "raw",
        PREFIX,
        version,
        url=get_url(version=version),
        name="sample_info.tsv",
        force=force,
        read_csv_kwargs=dict(sep=",", dtype=str),
    )


@click.command()
@verbose_option
def main():
    """Run the DepMap Cell Line CLI."""
    get_obo().write_default(write_obo=True)


if __name__ == "__main__":
    main()
