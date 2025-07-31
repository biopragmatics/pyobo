"""Get DrugCentral as OBO."""

import logging
from collections import defaultdict
from collections.abc import Iterable
from contextlib import closing

import bioregistry
import psycopg2
from pydantic import ValidationError
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Synonym, Term
from pyobo.struct.typedef import exact_match, has_inchi, has_smiles

__all__ = [
    "DrugCentralGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "drugcentral"

HOST = "unmtid-dbs.net"
PORT = 5433
USER = "drugman"
PASSWORD = "dosage"  # noqa:S105
DBNAME = "drugcentral"
PARAMS = {"dbname": DBNAME, "user": USER, "password": PASSWORD, "host": HOST, "port": PORT}


class DrugCentralGetter(Obo):
    """An ontology representation of the DrugCentral database."""

    ontology = bioversions_key = PREFIX
    typedefs = [exact_match, has_inchi, has_smiles]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


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
            xrefs: defaultdict[str, list[Reference]] = defaultdict(list)
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
                if xref_prefix_norm == "pdb.ligand":
                    # there is a weird invalid escaped \W appearing in pdb ligand ids
                    identifier = identifier.strip()

                try:
                    xref = Reference(prefix=xref_prefix_norm, identifier=identifier)
                except ValidationError:
                    # TODO mmsl is systematically incorrect, figure this out
                    if xref_prefix_norm != "mmsl":
                        tqdm.write(
                            f"[drugcentral:{drugcentral_id}] had invalid xref: {prefix}:{identifier}"
                        )
                    continue
                else:
                    xrefs[str(drugcentral_id)].append(xref)
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT id, name FROM public.synonyms")
            synonyms: defaultdict[str, list[Synonym]] = defaultdict(list)
            for drugcentral_id, synonym in cur.fetchall():
                synonyms[str(drugcentral_id)].append(Synonym(name=synonym))

    for drugcentral_id, name, cas, definition, inchi, smiles, inchi_key in structures:
        drugcentral_id = str(drugcentral_id)
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=drugcentral_id, name=name),
            definition=definition.replace("\n", " ") if definition else None,
            synonyms=synonyms.get(drugcentral_id, []),
            xrefs=xrefs.get(drugcentral_id, []),
        )
        if inchi_key:
            term.append_exact_match(Reference(prefix="inchikey", identifier=inchi_key))
        if smiles:
            term.annotate_string(has_smiles, smiles)
        if inchi:
            term.annotate_string(has_inchi, inchi)
        if cas:
            term.append_exact_match(Reference(prefix="cas", identifier=cas))
        yield term


if __name__ == "__main__":
    DrugCentralGetter.cli()
