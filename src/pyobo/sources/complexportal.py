# -*- coding: utf-8 -*-

"""Converter for ComplexPortal."""

import logging
from typing import Iterable, List, Tuple

import bioversions
import pandas as pd
from tqdm import tqdm

from pyobo import get_id_name_mapping
from pyobo.struct import Obo, Reference, Synonym, Term, from_species, has_part
from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "complexportal"
SPECIES = [
    "10090",
    "10116",
    "1235996",
    "1263720",
    "208964",
    "2697049",
    "284812",
    "3702",
    "559292",
    "562",
    "6239",
    "6523",
    "694009",
    "7227",
    "7787",
    "7788",
    "7955",
    "83333",
    "8355",
    "9031",
    "9606",
    "9615",
    "9823",
    "9913",
    "9940",
    "9986",
]
DTYPE = {
    "taxonomy_id": str,
}


def _parse_members(s) -> List[Tuple[Reference, str]]:
    if pd.isna(s):
        return []

    rv = []
    for member in s.split("|"):
        entity_id, count = member.split("(")
        count = count.rstrip(")")
        if ":" in entity_id:
            prefix, identifier = entity_id.split(":", 1)
        else:
            prefix, identifier = "uniprot", entity_id
        rv.append((Reference(prefix=prefix, identifier=identifier), count))
    return rv


def _parse_xrefs(s) -> List[Tuple[Reference, str]]:
    if pd.isna(s):
        return []

    rv = []
    for xref in s.split("|"):
        xref = xref.replace("protein ontology:PR:", "PR:")
        xref = xref.replace("protein ontology:PR_", "PR:")
        try:
            xref_curie, note = xref.split("(")
        except ValueError:
            logger.warning("xref missing (: %s", xref)
            continue
        note = note.rstrip(")")
        try:
            reference = Reference.from_curie(xref_curie)
        except ValueError:
            logger.warning("can not parse CURIE: %s", xref)
            continue
        if reference is None:
            logger.warning("reference is None after parsing: %s", xref)
            continue
        rv.append((reference, note))
    return rv


def get_obo() -> Obo:
    """Get the ComplexPortal OBO."""
    version = bioversions.get_version(PREFIX)

    return Obo(
        ontology=PREFIX,
        name="Complex Portal",
        data_version=version,
        iter_terms=get_terms,
        iter_terms_kwargs=dict(version=version),
        typedefs=[from_species, has_part],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_df(version: str) -> pd.DataFrame:
    """Get a combine ComplexPortal dataframe."""
    url_base = f"ftp://ftp.ebi.ac.uk/pub/databases/intact/complex/{version}/complextab"
    dfs = [
        ensure_df(
            PREFIX,
            url=f"{url_base}/{ncbitaxonomy_id}.tsv",
            version=version,
            na_values={"-"},
            header=0,
            dtype=str,
        )
        for ncbitaxonomy_id in SPECIES
    ]
    return pd.concat(dfs)


def get_terms(version: str) -> Iterable[Term]:
    """Get ComplexPortal terms."""
    df = get_df(version=version)
    df.rename(
        inplace=True,
        columns={
            "Aliases for complex": "aliases",
            "Identifiers (and stoichiometry) of molecules in complex": "members",
            "Taxonomy identifier": "taxonomy_id",
            "Cross references": "xrefs",
            "Description": "definition",
            "Recommended name": "name",
            "#Complex ac": "complexportal_id",
        },
    )

    df["aliases"] = df["aliases"].map(lambda s: s.split("|") if pd.notna(s) else [])
    df["members"] = df["members"].map(_parse_members)
    df["xrefs"] = df["xrefs"].map(_parse_xrefs)

    taxnomy_id_to_name = get_id_name_mapping("ncbitaxon")
    df["taxonomy_name"] = df["taxonomy_id"].map(taxnomy_id_to_name.get)

    slim_df = df[
        [
            "complexportal_id",
            "name",
            "definition",
            "aliases",
            "xrefs",
            "taxonomy_id",
            "taxonomy_name",
            "members",
        ]
    ]
    it = tqdm(slim_df.values, total=len(slim_df.index), desc=f"mapping {PREFIX}")
    unhandled_xref_type = set()
    for (
        complexportal_id,
        name,
        definition,
        aliases,
        xrefs,
        taxonomy_id,
        taxonomy_name,
        members,
    ) in it:
        synonyms = [Synonym(name=alias) for alias in aliases]
        _xrefs = []
        provenance = []
        for reference, note in xrefs:
            if note == "identity":
                _xrefs.append(reference)
            elif note == "see-also" and reference.prefix == "pubmed":
                provenance.append(reference)
            elif (note, reference.prefix) not in unhandled_xref_type:
                logger.debug(f"unhandled xref type: {note} / {reference.prefix}")
                unhandled_xref_type.add((note, reference.prefix))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=complexportal_id, name=name),
            definition=definition.strip() if pd.notna(definition) else None,
            synonyms=synonyms,
            xrefs=_xrefs,
            provenance=provenance,
        )
        term.set_species(identifier=taxonomy_id, name=taxonomy_name)

        for reference, _count in members:
            term.append_relationship(has_part, reference)

        yield term


if __name__ == "__main__":
    get_obo().write_default()
