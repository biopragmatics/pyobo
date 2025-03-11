"""Converter for InterPro."""

from collections import defaultdict
from collections.abc import Iterable, Mapping

from .utils import get_go_mapping
from ..struct import Obo, Reference, Term
from ..struct.typedef import enables, has_category, has_member
from ..utils.io import multisetdict
from ..utils.path import ensure_df, ensure_path

__all__ = [
    "InterProGetter",
]

PREFIX = "interpro"

#: Data source for protein-interpro mappings
INTERPRO_PROTEIN_COLUMNS = [
    "uniprot_id",
    "interpro_id",
    "interpro_name",
    "xref",  # either superfamily, gene family gene scan, PFAM, TIGERFAM
    "start",  # int
    "end",  # int
]


class InterProGetter(Obo):
    """An ontology representation of InterPro."""

    ontology = bioversions_key = PREFIX
    typedefs = [enables, has_member, has_category]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over InterPro terms."""
        return iter_terms(version=self._version_or_raise, force=force)


def iter_terms(*, version: str, proteins: bool = False, force: bool = False) -> Iterable[Term]:
    """Get InterPro terms."""
    parents = get_interpro_tree(version=version, force=force)
    interpro_to_gos = get_interpro_go_df(version=version, force=force)
    interpro_to_proteins = (
        get_interpro_to_proteins_df(version=version, force=force) if proteins else {}
    )

    entries_df = ensure_df(
        PREFIX,
        url=f"https://ftp.ebi.ac.uk/pub/databases/interpro/releases/{version}/entry.list",
        name="entries.tsv",
        skiprows=1,
        names=("ENTRY_AC", "ENTRY_TYPE", "ENTRY_NAME"),
        version=version,
        force=force,
    )

    references = {
        identifier: Reference(prefix=PREFIX, identifier=identifier, name=name)
        for identifier, _, name in entries_df.values
    }

    for identifier, entry_type, _ in entries_df.values:
        term = Term(
            reference=references[identifier],
            parents=[references[parent_id] for parent_id in parents.get(identifier, [])],
        )
        for go_id, go_name in interpro_to_gos.get(identifier, []):
            term.append_relationship(
                enables, Reference(prefix="go", identifier=go_id, name=go_name)
            )
        term.annotate_string(has_category, entry_type)
        for uniprot_id in interpro_to_proteins.get(identifier, []):
            term.append_relationship(has_member, Reference(prefix="uniprot", identifier=uniprot_id))
        yield term


def get_interpro_go_df(version: str, force: bool = False) -> Mapping[str, set[tuple[str, str]]]:
    """Get InterPro to Gene Ontology molecular function mapping."""
    url = f"https://ftp.ebi.ac.uk/pub/databases/interpro/releases/{version}/interpro2go"
    path = ensure_path(PREFIX, url=url, name="interpro2go.tsv", version=version, force=force)
    return get_go_mapping(path, prefix=PREFIX)


def get_interpro_tree(version: str, force: bool = False):
    """Get InterPro Data source."""
    url = f"https://ftp.ebi.ac.uk/pub/databases/interpro/releases/{version}/ParentChildTreeFile.txt"
    path = ensure_path(PREFIX, url=url, version=version, force=force)
    with path.open() as f:
        return _parse_tree_helper(f)


def _parse_tree_helper(lines: Iterable[str]):
    rv1: defaultdict[str, list[str]] = defaultdict(list)
    previous_depth, previous_id = 0, ""
    stack = [previous_id]

    for line in lines:
        depth = _count_front(line)
        parent_id, _ = line[depth:].split("::", maxsplit=1)

        if depth == 0:
            stack.clear()
            stack.append(parent_id)
        else:
            if depth > previous_depth:
                stack.append(previous_id)

            elif depth < previous_depth:
                del stack[-1]

            child_id = stack[-1]
            rv1[child_id].append(parent_id)  # type:ignore

        previous_depth, previous_id = depth, parent_id

    rv2 = defaultdict(list)
    for k, vs in rv1.items():
        for v in vs:
            rv2[v].append(k)
    return dict(rv2)


def _count_front(s: str) -> int:
    """Count the number of leading dashes on a string."""
    for position, element in enumerate(s):
        if element != "-":
            return position
    raise ValueError


def get_interpro_to_proteins_df(version: str, force: bool = False):
    """Get InterPro to Protein dataframe."""
    url = f"https://ftp.ebi.ac.uk/pub/databases/interpro/releases/{version}/protein2ipr.dat.gz"
    df = ensure_df(
        PREFIX,
        url=url,
        compression="gzip",
        usecols=[0, 1, 3],
        names=INTERPRO_PROTEIN_COLUMNS,
        version=version,
        force=force,
    )
    return multisetdict((interpro_id, uniprot_id) for uniprot_id, interpro_id in df.values)


if __name__ == "__main__":
    InterProGetter.cli()
