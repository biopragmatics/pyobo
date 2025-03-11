"""DepMap cell lines."""

from collections.abc import Iterable

import pandas as pd
import pystow

from pyobo import Obo, Reference, Term
from pyobo.struct.typedef import exact_match

__all__ = [
    "DepMapGetter",
]

PREFIX = "depmap"
VERSION = "21Q2"


class DepMapGetter(Obo):
    """An ontology representation of the Cancer Dependency Map's cell lines."""

    ontology = bioversions_key = PREFIX
    data_version = VERSION
    typedefs = [exact_match]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_url(version: str | None = None) -> str:
    """Get the URL for the given version of the DepMap cell line metadata file.

    :param version: The version of the data

    :returns: The URL as a string for downloading the dat

    .. warning::

        This does not currently take the version into account. Need to write a crawler
        since data is not easy to access.
    """
    #: This is the DepMap Public 21Q2 version. There isn't a way to do this automatically without writing a crawler
    url = "https://ndownloader.figshare.com/files/27902376"
    return url


def _fix_mangled_int(x: str) -> str | None:
    return str(int(float(x))) if pd.notna(x) else None


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
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
        if pd.isna(name):
            if pd.notna(sname):
                name, sname = sname, None
            else:
                name = None
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
            term.append_exact_match(Reference(prefix="cosmic.cell", identifier=cosmic_id))
        if pd.notna(cellosaurus_id):
            term.append_exact_match(Reference(prefix="cellosaurus", identifier=cellosaurus_id))

        # WTSI stands for welcome trust sanger institute
        # Not sure where this prefix goes
        # if pd.notna(wtsi_id):
        #    term.append_xref(Reference("sanger", wtsi_id))

        # Not sure what this is
        # if pd.notna(sanger_id):
        #    term.append_xref(Reference("sanger", sanger_id))

        # TODO There's lots of other great ontological information in here. Next time.
        yield term


def ensure(version: str, force: bool = False) -> pd.DataFrame:
    """Ensure and parse the given version of the DepMap cell line metadata."""
    return pystow.ensure_csv(
        "pyobo",
        "raw",
        PREFIX,
        version,
        url=get_url(version=version),
        name="sample_info.tsv",
        force=force,
        read_csv_kwargs={"sep": ",", "dtype": str},
    )


if __name__ == "__main__":
    DepMapGetter.cli()
