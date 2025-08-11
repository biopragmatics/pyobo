"""Converter for IntAct complexes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import pandas as pd
from pydantic import ValidationError
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

__all__ = [
    "IntactGetter",
]

PREFIX = "intact"
COMPLEXPORTAL_MAPPINGS_UNVERSIONED = (
    "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/various/cpx_ebi_ac_translation.txt"
)
REACTOME_MAPPINGS_UNVERSIONED = (
    "https://ftp.ebi.ac.uk/pub/databases/intact/current/various/reactome.dat"
)


# TODO it looks like it's probably also the case that
#  this semantic space contains IDs for proteins/
#  interactors. These need to be added too


class IntactGetter(Obo):
    """An ontology representation of Intact."""

    bioversions_key = ontology = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self._version_or_raise)


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get terms from the Contributor Roles Taxonomy via GitHub."""
    cplx = _get_mappings(
        COMPLEXPORTAL_MAPPINGS_UNVERSIONED, "complexportal", version=version, force=force
    )
    reactome = _get_mappings(
        REACTOME_MAPPINGS_UNVERSIONED, "reactome", version=version, force=force
    )
    for intact_id in sorted(set(cplx).union(reactome)):
        term = Term.from_triple(PREFIX, intact_id)
        for complexportal_xref in sorted(cplx.get(intact_id, [])):
            term.append_exact_match(complexportal_xref)
        for reactome_xref in sorted(reactome.get(intact_id, [])):
            term.append_xref(reactome_xref)
        yield term


def _get_mappings(
    url: str, target_prefix: str, version: str, *, force: bool = False
) -> dict[str, set[Reference]]:
    path = ensure_path(PREFIX, url=url, version=version, force=force)
    df = pd.read_csv(path, sep="\t", header=None, usecols=[0, 1])

    dd = defaultdict(set)
    for intact_id, target_identifier in df.values:
        try:
            obj = Reference(prefix=target_prefix, identifier=target_identifier)
        except ValidationError:
            tqdm.write(f"[intact:{intact_id}] invalid xref: {target_prefix}:{target_identifier}")
            continue
        dd[intact_id].add(obj)

    return dict(dd)


if __name__ == "__main__":
    IntactGetter.cli()
