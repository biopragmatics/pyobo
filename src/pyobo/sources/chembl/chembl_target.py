"""Converter for ChEMBL targets."""

import logging
from collections import defaultdict
from collections.abc import Iterable

import chembl_downloader
from tqdm import tqdm

from pyobo import default_reference
from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import (
    exact_match,
    has_component,
    has_member,
    has_participant,
)

__all__ = [
    "ChEMBLTargetGetter",
]

from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "chembl.target"

TTYPE_QUERY = """\
SELECT TARGET_TYPE, TARGET_DESC, PARENT_TYPE
FROM TARGET_TYPE
"""

QUERY = """\
SELECT
    CHEMBL_ID,
    PREF_NAME,
    TARGET_TYPE,
    TAX_ID
FROM TARGET_DICTIONARY
"""


class ChEMBLTargetGetter(Obo):
    """An ontology representation of ChEMBL targets."""

    ontology = PREFIX
    bioversions_key = "chembl"
    typedefs = [exact_match, has_component, has_member, has_participant]
    root_terms = [
        default_reference(PREFIX, "undefined"),
        default_reference(PREFIX, "molecular"),
        default_reference(PREFIX, "non-molecular"),
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over ChEMBL targets."""
    chembl_to_uniprots = get_chembl_protein_equivalences(version=version)
    target_types: dict[str, Term] = {}
    parents: dict[str, str] = {}
    with chembl_downloader.cursor(version=version) as cursor:
        cursor.execute(TTYPE_QUERY)
        for target_type, desc, parent in cursor.fetchall():
            identifier = target_type.lower().replace(" ", "-")
            target_types[target_type] = Term(
                reference=default_reference(PREFIX, identifier, name=target_type),
                definition=desc,
            )
            if parent:
                parents[target_type] = parent

        for child, parent in parents.items():
            target_types[child].append_parent(target_types[parent])

        yield from target_types.values()

    with chembl_downloader.cursor(version=version) as cursor:
        cursor.execute(QUERY)
        for chembl_id, name, target_type, ncbitaxon_id in cursor.fetchall():
            term = Term.from_triple(prefix=PREFIX, identifier=chembl_id, name=name)
            if ncbitaxon_id:
                term.set_species(str(ncbitaxon_id))
            term.append_parent(target_types[target_type])

            uniprot_ids = chembl_to_uniprots.get(chembl_id)
            if uniprot_ids is None:
                pass
            elif target_type in {
                "PROTEIN COMPLEX",
                "CHIMERIC PROTEIN",
                "PROTEIN COMPLEX GROUP",
                "PROTEIN NUCLEIC-ACID COMPLEX",
                "SELECTIVITY GROUP",
            }:
                for uniprot_id in uniprot_ids:
                    term.annotate_object(
                        has_component, Reference(prefix="uniprot", identifier=uniprot_id)
                    )
            elif target_type == "PROTEIN FAMILY":
                for uniprot_id in uniprot_ids:
                    term.annotate_object(
                        has_member, Reference(prefix="uniprot", identifier=uniprot_id)
                    )
            elif target_type == "PROTEIN-PROTEIN INTERACTION":
                for uniprot_id in uniprot_ids:
                    term.annotate_object(
                        has_participant, Reference(prefix="uniprot", identifier=uniprot_id)
                    )
            elif target_type == "SINGLE PROTEIN":
                if len(uniprot_ids) == 1:
                    term.append_exact_match(Reference(prefix="uniprot", identifier=uniprot_ids[0]))
                else:
                    tqdm.write(
                        f"[chembl.target:{chembl_id}] multiple mappings found to single protein: {uniprot_ids}"
                    )
                    for uniprot_id in uniprot_ids:
                        term.append_xref(Reference(prefix="uniprot", identifier=uniprot_id))
            elif len(uniprot_ids) == 1:
                luid = uniprot_ids[0]
                if luid.startswith("ENSG"):
                    reference = Reference(prefix="ensembl", identifier=luid)
                else:
                    reference = Reference(prefix="uniprot", identifier=luid)
                term.append_exact_match(reference)
            else:
                tqdm.write(
                    f"[chembl.target:{chembl_id}] need to handle multiple uniprots for {target_type} - {uniprot_ids}"
                )

            yield term


def get_chembl_protein_equivalences(version: str | None = None) -> dict[str, list[str]]:
    """Get ChEMBL protein equivalences."""
    if version is None:
        version = chembl_downloader.latest()
    url = f"ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{version}/chembl_uniprot_mapping.txt"
    df = ensure_df(
        PREFIX,
        url=url,
        sep="\t",
        skiprows=1,
        usecols=[0, 1],
        names=["uniprot", "chembl"],
        header=None,
        # names=[TARGET_ID, SOURCE_ID],  # switch around
    )
    dd = defaultdict(list)
    for uniprot, chembl in df.values:
        dd[chembl].append(uniprot)
    return dict(dd)


if __name__ == "__main__":
    ChEMBLTargetGetter.cli()
