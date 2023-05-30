# -*- coding: utf-8 -*-

"""Get DrugCentral as OBO."""

import logging
from collections import defaultdict
from contextlib import closing
from typing import DefaultDict, Iterable, List

import bioregistry
import psycopg2
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Synonym, Term

__all__ = [
    "DrugCentralGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "drugcentral"

HOST = "unmtid-dbs.net"
PORT = 5433
USER = "drugman"
PASSWORD = "dosage"
DBNAME = "drugcentral"
PARAMS = dict(dbname=DBNAME, user=USER, password=PASSWORD, host=HOST, port=PORT)


class DrugCentralGetter(Obo):
    """An ontology representation of the DrugCentral database."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def get_obo(force: bool = False) -> Obo:
    """Get DrugCentral OBO."""
    return DrugCentralGetter(force=force)


def iter_terms() -> Iterable[Term]:
    """Iterate over DrugCentral terms."""
    with closing(psycopg2.connect(**PARAMS)) as conn:
        with closing(conn.cursor()) as cur:
            cur.execute(
                "SELECT cd_id, name, cas_reg_no, mrdef, inchi, smiles, inchikey FROM public.structures"
            )
            structures = cur.fetchall()

        with closing(conn.cursor()) as cur:
            cur.execute("SELECT struct_id, id_type, identifier FROM public.identifier")
            rows = cur.fetchall()
            xrefs: DefaultDict[str, List[Reference]] = defaultdict(list)
            for drugcentral_id, prefix, identifier in tqdm(
                rows, unit_scale=True, desc="loading xrefs"
            ):
                if not identifier or not prefix:
                    continue
                if prefix == "ChEMBL_ID":
                    prefix = "chembl.compound"
                xref_prefix_norm = bioregistry.normalize_prefix(prefix)
                if xref_prefix_norm is None:
                    tqdm.write(f"did not normalize {prefix}:{identifier}")
                    continue
                identifier = bioregistry.standardize_identifier(xref_prefix_norm, identifier)
                xrefs[str(drugcentral_id)].append(
                    Reference(prefix=xref_prefix_norm, identifier=identifier)
                )
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT id, name FROM public.synonyms")
            synonyms: DefaultDict[str, List[Synonym]] = defaultdict(list)
            for drugcentral_id, synonym in cur.fetchall():
                synonyms[str(drugcentral_id)].append(Synonym(name=synonym))

    for drugcentral_id, name, cas, definition, inchi, smiles, inchi_key in structures:
        drugcentral_id = str(drugcentral_id)
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=drugcentral_id, name=name),
            definition=definition,
            synonyms=synonyms.get(drugcentral_id, []),
            xrefs=xrefs.get(drugcentral_id, []),
        )
        if inchi_key:
            term.append_xref(Reference(prefix="inchikey", identifier=inchi_key))
        term.append_property("smiles", smiles)
        term.append_property("inchi", inchi)
        if cas:
            term.append_xref(Reference(prefix="cas", identifier=cas))
        yield term


if __name__ == "__main__":
    DrugCentralGetter.cli()
