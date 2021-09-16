# -*- coding: utf-8 -*-

"""Converter for ZFIN."""

import logging
from collections import defaultdict
from typing import Iterable

import bioversions
import click
from more_click import verbose_option
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term, from_species, has_gene_product, orthologous
from pyobo.utils.io import multidict, multisetdict
from pyobo.utils.path import ensure_df

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


def get_obo(force: bool = False) -> Obo:
    """Get ZFIN OBO."""
    version = bioversions.get_version("zfin")
    return Obo(
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force),
        name=NAME,
        ontology=PREFIX,
        typedefs=[from_species, has_gene_product, orthologous],
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
    )


MARKERS_COLUMNS = [
    "zfin_id",
    "name",
    "description",
    "supertype",
    "sequence_ontology_id",
]


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get terms."""
    alt_ids_df = ensure_df(
        PREFIX, url=ALTS_URL, name="alts.tsv", force=force, header=None, names=["alt", "zfin_id"]
    )
    primary_to_alt_ids = defaultdict(set)
    for alt_id, zfin_id in alt_ids_df.values:
        primary_to_alt_ids[zfin_id].add(alt_id)

    human_orthologs = multisetdict(
        ensure_df(PREFIX, url=HUMAN_ORTHOLOGS, force=force, header=None, usecols=[0, 7]).values
    )
    mouse_orthologs = multisetdict(
        ensure_df(PREFIX, url=MOUSE_ORTHOLOGS, force=force, header=None, usecols=[0, 5]).values
    )
    fly_orthologs = multisetdict(
        ensure_df(PREFIX, url=FLY_ORTHOLOGS, force=force, header=None, usecols=[0, 5]).values
    )
    entrez_mappings = dict(
        ensure_df(PREFIX, url=ENTREZ_MAPPINGS, force=force, header=None, usecols=[0, 3]).values
    )
    uniprot_mappings = multidict(
        ensure_df(PREFIX, url=UNIPROT_MAPPINGS, force=force, header=None, usecols=[0, 3]).values
    )

    df = ensure_df(
        PREFIX, url=URL, name="markers.tsv", force=force, header=None, names=MARKERS_COLUMNS
    )
    df["sequence_ontology_id"] = df["sequence_ontology_id"].map(lambda x: x[len("SO:") :])
    so = {
        sequence_ontology_id: Reference.auto(prefix="SO", identifier=sequence_ontology_id)
        for sequence_ontology_id in df["sequence_ontology_id"].unique()
    }
    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for identifier, name, definition, _entity_type, sequence_ontology_id in tqdm(df.values):
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
            term.append_xref(Reference("ncbigene", entrez_id))
        for uniprot_id in uniprot_mappings.get(identifier, []):
            term.append_relationship(has_gene_product, Reference.auto("uniprot", uniprot_id))
        for hgnc_id in human_orthologs.get(identifier, []):
            term.append_relationship(orthologous, Reference.auto("hgnc", hgnc_id))
        for mgi_curie in mouse_orthologs.get(identifier, []):
            term.append_relationship(orthologous, Reference.from_curie(mgi_curie, auto=True))
        for flybase_id in fly_orthologs.get(identifier, []):
            term.append_relationship(orthologous, Reference("flybase", flybase_id))

        yield term


@click.command()
@verbose_option
def _main():
    obo = get_obo(force=True)
    obo.write_default(force=True, write_obo=True)


if __name__ == "__main__":
    _main()
