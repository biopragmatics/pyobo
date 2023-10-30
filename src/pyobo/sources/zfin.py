# -*- coding: utf-8 -*-

"""Converter for ZFIN."""

import logging
from collections import defaultdict
from typing import Iterable, Optional

from tqdm.auto import tqdm

from pyobo.struct import (
    Obo,
    Reference,
    Term,
    from_species,
    has_gene_product,
    orthologous,
)
from pyobo.utils.io import multidict, multisetdict
from pyobo.utils.path import ensure_df

__all__ = [
    "ZFINGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "zfin"
NAME = "Zebrafish Information Network"
URL = "https://zfin.org/downloads/genetic_markers.txt"
ALTS_URL = "https://zfin.org/downloads/zdb_history.txt"
HUMAN_ORTHOLOGS = "https://zfin.org/downloads/human_orthos.txt"
MOUSE_ORTHOLOGS = "https://zfin.org/downloads/mouse_orthos.txt"
FLY_ORTHOLOGS = "https://zfin.org/downloads/fly_orthos.txt"
ENTREZ_MAPPINGS = "https://zfin.org/downloads/gene.txt"
UNIPROT_MAPPINGS = "https://zfin.org/downloads/uniprot.txt"


class ZFINGetter(Obo):
    """An ontology representation of ZFIN's zebrafish database."""

    bioversions_key = ontology = PREFIX
    typedefs = [from_species, has_gene_product, orthologous]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in ZFIN."""
        return get_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get ZFIN OBO."""
    return ZFINGetter(force=force)


MARKERS_COLUMNS = [
    "zfin_id",
    "name",
    "description",
    "supertype",
    "sequence_ontology_id",
]


def get_terms(force: bool = False, version: Optional[str] = None) -> Iterable[Term]:
    """Get terms."""
    alt_ids_df = ensure_df(
        PREFIX,
        url=ALTS_URL,
        name="alts.tsv",
        force=force,
        header=None,
        names=["alt", "zfin_id"],
        version=version,
    )
    primary_to_alt_ids = defaultdict(set)
    for alt_id, zfin_id in alt_ids_df.values:
        primary_to_alt_ids[zfin_id].add(alt_id)

    human_orthologs = multisetdict(
        ensure_df(
            PREFIX, url=HUMAN_ORTHOLOGS, force=force, header=None, usecols=[0, 7], version=version
        ).values
    )
    mouse_orthologs = multisetdict(
        ensure_df(
            PREFIX, url=MOUSE_ORTHOLOGS, force=force, header=None, usecols=[0, 5], version=version
        ).values
    )
    fly_orthologs = multisetdict(
        ensure_df(
            PREFIX, url=FLY_ORTHOLOGS, force=force, header=None, usecols=[0, 5], version=version
        ).values
    )
    entrez_mappings = dict(
        ensure_df(
            PREFIX, url=ENTREZ_MAPPINGS, force=force, header=None, usecols=[0, 3], version=version
        ).values
    )
    uniprot_mappings = multidict(
        ensure_df(
            PREFIX, url=UNIPROT_MAPPINGS, force=force, header=None, usecols=[0, 3], version=version
        ).values
    )

    df = ensure_df(
        PREFIX,
        url=URL,
        name="markers.tsv",
        force=force,
        header=None,
        names=MARKERS_COLUMNS,
        version=version,
    )
    df["sequence_ontology_id"] = df["sequence_ontology_id"].map(lambda x: x[len("SO:") :])
    so = {
        sequence_ontology_id: Reference.auto(prefix="SO", identifier=sequence_ontology_id)
        for sequence_ontology_id in df["sequence_ontology_id"].unique()
    }
    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for identifier, name, definition, _entity_type, sequence_ontology_id in tqdm(
        df.values, unit_scale=True, unit="gene", desc="zfin"
    ):
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=name,
            definition=definition if definition != name else None,
        )
        term.set_species(identifier="7955", name="Danio rerio")
        term.append_parent(so[sequence_ontology_id])
        # Entity type is redundant of identifier
        # term.append_property("type", entity_type)
        for alt_id in primary_to_alt_ids[identifier]:
            term.append_alt(alt_id)
        entrez_id = entrez_mappings.get(identifier)
        if entrez_id:
            term.append_exact_match(Reference(prefix="ncbigene", identifier=entrez_id))
        for uniprot_id in uniprot_mappings.get(identifier, []):
            term.append_relationship(has_gene_product, Reference.auto("uniprot", uniprot_id))
        for hgnc_id in human_orthologs.get(identifier, []):
            term.append_relationship(orthologous, Reference.auto("hgnc", hgnc_id))
        for mgi_curie in mouse_orthologs.get(identifier, []):
            mouse_ortholog = Reference.from_curie(mgi_curie, auto=True)
            if mouse_ortholog:
                term.append_relationship(orthologous, mouse_ortholog)
        for flybase_id in fly_orthologs.get(identifier, []):
            term.append_relationship(orthologous, Reference.auto("flybase", flybase_id))

        yield term


if __name__ == "__main__":
    ZFINGetter.cli()
