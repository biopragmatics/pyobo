# -*- coding: utf-8 -*-

"""Converter for Rhea."""

import logging
from typing import TYPE_CHECKING, Dict, Iterable, Optional

import bioversions
import pystow

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import (
    TypeDef,
    enabled_by,
    has_bidirectional_reaction,
    has_input,
    has_left_to_right_reaction,
    has_output,
    has_participant,
    has_right_to_left_reaction,
    reaction_enabled_by_molecular_function,
)
from pyobo.utils.path import ensure_df

if TYPE_CHECKING:
    import rdflib

__all__ = [
    "RheaGetter",
]

logger = logging.getLogger(__name__)
PREFIX = "rhea"
RHEA_RDF_GZ_URL = "ftp://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz"


class RheaGetter(Obo):
    """An ontology representation of Rhea's chemical reaction database."""

    ontology = bioversions_key = PREFIX
    typedefs = [
        has_left_to_right_reaction,
        has_bidirectional_reaction,
        has_right_to_left_reaction,
        enabled_by,
        has_input,
        has_output,
        has_participant,
        reaction_enabled_by_molecular_function,
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get Rhea as OBO."""
    return RheaGetter(force=force)


def ensure_rhea_rdf(version: Optional[str] = None, force: bool = False) -> "rdflib.Graph":
    """Get the Rhea RDF graph."""
    # see docs: https://ftp.expasy.org/databases/rhea/rdf/rhea_rdf_documentation.pdf
    if version is None:
        version = bioversions.get_version(PREFIX)
    return pystow.ensure_rdf(
        "pyobo",
        "raw",
        PREFIX,
        version,
        url=RHEA_RDF_GZ_URL,
        force=force,
        parse_kwargs=dict(format="xml"),
    )


def _get_lr_name(name: str) -> str:
    return name.replace(" = ", " => ")


def _get_rl_name(name: str) -> str:
    left, right = name.split(" = ", 1)
    return f"{right} => {left}"


def _get_bi_name(name: str) -> str:
    return name.replace(" = ", " <=> ")


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in Rhea."""
    graph = ensure_rhea_rdf(version=version, force=force)
    result = graph.query(
        """\
        PREFIX rh:<http://rdf.rhea-db.org/>
        SELECT ?reaction ?reactionId ?reactionLabel WHERE {
          ?reaction rdfs:subClassOf rh:Reaction ;
                    rh:id ?reactionId ;
                    rdfs:label ?reactionLabel .
        }
    """
    )
    names = {str(identifier): str(name) for _, identifier, name in result}

    terms: Dict[str, Term] = {}
    master_to_left: Dict[str, str] = {}
    master_to_right: Dict[str, str] = {}
    master_to_bi: Dict[str, str] = {}

    directions = ensure_df(
        PREFIX,
        url="ftp://ftp.expasy.org/databases/rhea/tsv/rhea-directions.tsv",
        version=version,
        force=force,
    )
    for master, lr, rl, bi in directions.values:
        master_to_left[master] = lr
        master_to_right[master] = rl
        master_to_bi[master] = bi

        name = names[master]

        terms[master] = Term(reference=Reference(prefix=PREFIX, identifier=master, name=name))
        terms[lr] = Term(reference=Reference(prefix=PREFIX, identifier=lr, name=_get_lr_name(name)))
        terms[rl] = Term(reference=Reference(prefix=PREFIX, identifier=rl, name=_get_rl_name(name)))
        terms[bi] = Term(reference=Reference(prefix=PREFIX, identifier=bi, name=_get_bi_name(name)))

        terms[master].append_relationship(has_left_to_right_reaction, terms[lr])
        terms[master].append_relationship(has_right_to_left_reaction, terms[rl])
        terms[master].append_relationship(has_bidirectional_reaction, terms[bi])
        terms[lr].append_parent(terms[master])
        terms[rl].append_parent(terms[master])
        terms[bi].append_parent(terms[master])

    # inspired by https://github.com/geneontology/go-ontology/blob/master/src/sparql/construct-rhea-reactions.sparql
    sparql = """\
    PREFIX rh:<http://rdf.rhea-db.org/>
    SELECT ?reactionId ?side ?chebi WHERE {
      ?reaction rdfs:subClassOf rh:Reaction ;
                rh:id ?reactionId .

      ?reaction rh:side ?side .
      ?side rh:contains ?participant .
      ?participant rh:compound ?compound .
      ?compound rh:chebi|rh:underlyingChebi|(rh:reactivePart/rh:chebi) ?chebi .
    }
    """
    for master_rhea_id, side_uri, chebi_uri in graph.query(sparql):
        master_rhea_id = str(master_rhea_id)
        chebi_reference = Reference(
            prefix="chebi", identifier=chebi_uri[len("http://purl.obolibrary.org/obo/CHEBI_") :]
        )
        side = side_uri.split("_")[-1]  # L or R
        if side == "L":
            left_rhea_id = master_to_left[master_rhea_id]
            right_rhea_id = master_to_right[master_rhea_id]
        elif side == "R":
            left_rhea_id = master_to_right[master_rhea_id]
            right_rhea_id = master_to_left[master_rhea_id]
        else:
            raise ValueError(f"Invalid side: {side_uri}")
        terms[master_rhea_id].append_relationship(has_participant, chebi_reference)
        terms[master_to_bi[master_rhea_id]].append_relationship(has_participant, chebi_reference)
        terms[left_rhea_id].append_relationship(has_input, chebi_reference)
        terms[right_rhea_id].append_relationship(has_output, chebi_reference)

    hierarchy = ensure_df(
        PREFIX,
        url="ftp://ftp.expasy.org/databases/rhea/tsv/rhea-relationships.tsv",
        version=version,
        force=force,
    )
    for source, relation, target in hierarchy.values:
        if relation != "is_a":
            raise ValueError(f"RHEA unrecognized relation: {relation}")
        terms[source].append_parent(terms[target])

    for xref_prefix, url, relation in [
        ("ecocyc", "rhea2ecocyc", None),
        ("kegg.reaction", "rhea2kegg_reaction", None),
        ("reactome", "rhea2reactome", None),
        ("macie", "rhea2macie", None),
        ("metacyc", "rhea2metacyc", None),
        ("go", "rhea2go", reaction_enabled_by_molecular_function),
        ("uniprot", "rhea2uniprot", enabled_by),
    ]:
        xref_df = ensure_df(
            PREFIX,
            url=f"ftp://ftp.expasy.org/databases/rhea/tsv/{url}.tsv",
            version=version,
            force=force,
        )
        for directional_rhea_id, _direction, _master_rhea_id, xref_id in xref_df.values:
            if directional_rhea_id not in terms:
                logger.debug(
                    "[%s] could not find %s:%s for xref %s:%s",
                    PREFIX,
                    PREFIX,
                    directional_rhea_id,
                    xref_prefix,
                    xref_id,
                )
                continue
            target_reference = Reference(prefix=xref_prefix, identifier=xref_id)
            if isinstance(relation, TypeDef):
                terms[directional_rhea_id].append_relationship(relation, target_reference)
            else:
                terms[directional_rhea_id].append_xref(target_reference)

    ec_df = ensure_df(
        PREFIX,
        url="ftp://ftp.expasy.org/databases/rhea/tsv/rhea-ec-iubmb.tsv",
        version=version,
        force=force,
    )
    for (
        directional_rhea_id,
        _status,
        _direction,
        _master_id,
        ec,
        _enzyme_status,
        _iubmb,
    ) in ec_df.values:
        terms[directional_rhea_id].append_relationship(
            enabled_by, Reference(prefix="eccode", identifier=ec)
        )

    yield from terms.values()


if __name__ == "__main__":
    RheaGetter().write_default(write_obo=True, force=True)
