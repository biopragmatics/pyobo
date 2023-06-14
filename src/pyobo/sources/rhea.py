# -*- coding: utf-8 -*-

"""Converter for Rhea."""

import logging
from typing import Iterable

import pystow

from pyobo.struct import Obo, Reference, Term, TypeDef
from pyobo.utils.path import ensure_df

__all__ = [
    "RheaGetter",
]

logger = logging.getLogger(__name__)
PREFIX = "rhea"

has_lr = TypeDef(Reference(prefix=PREFIX, identifier="has_lr_reaction"))
has_rl = TypeDef(Reference(prefix=PREFIX, identifier="has_rl_reaction"))
has_bi = TypeDef(Reference(prefix=PREFIX, identifier="has_bi_reaction"))


class RheaGetter(Obo):
    """An ontology representation of Rhea's chemical reaction database."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_lr, has_bi, has_rl]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get Rhea as OBO."""
    return RheaGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over terms in Rhea."""
    terms = {}

    directions = ensure_df(
        PREFIX,
        url="ftp://ftp.expasy.org/databases/rhea/tsv/rhea-directions.tsv",
        version=version,
        force=force,
    )
    for master, lr, rl, bi in directions.values:
        terms[master] = Term(reference=Reference(PREFIX, master))
        terms[lr] = Term(reference=Reference(PREFIX, lr))
        terms[rl] = Term(reference=Reference(PREFIX, rl))
        terms[bi] = Term(reference=Reference(PREFIX, bi))

        terms[master].append_relationship(has_lr, terms[lr])
        terms[master].append_relationship(has_rl, terms[rl])
        terms[master].append_relationship(has_bi, terms[bi])
        terms[lr].append_parent(terms[master])
        terms[rl].append_parent(terms[master])
        terms[bi].append_parent(terms[master])

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

    for xref_prefix, url in [
        ("ecocyc", "rhea2ecocyc"),
        ("kegg.reaction", "rhea2kegg_reaction"),
        ("reactome", "rhea2reactome"),
        ("macie", "rhea2macie"),
        ("metacyc", "rhea2metacyc"),
    ]:
        xref_df = ensure_df(
            PREFIX,
            url=f"ftp://ftp.expasy.org/databases/rhea/tsv/{url}.tsv",
            version=version,
            force=force,
        )
        for rhea_id, _, _, xref_id in xref_df.values:
            if rhea_id not in terms:
                logger.debug(
                    "[%s] could not find %s:%s for xref %s:%s",
                    PREFIX,
                    PREFIX,
                    rhea_id,
                    xref_prefix,
                    xref_id,
                )
                continue
            terms[rhea_id].append_xref(Reference(xref_prefix, xref_id))

    # TODO are EC codes equivalent?
    # TODO uniprot enabled by (RO:0002333)
    # TODO names?

    url = "ftp://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz"
    graph = pystow.ensure_rdf(
        "pyobo", "raw", PREFIX, version, url=url, force=force, parse_kwargs=dict(format="xml")
    )
    result = graph.query(
        """
    PREFIX rh:<http://rdf.rhea-db.org/>
    SELECT ?reaction ?reactionId ?reactionLabel WHERE {
      ?reaction rdfs:subClassOf rh:Reaction .
      ?reaction rh:id ?reactionId .
      ?reaction rdfs:label ?reactionLabel .
    }
    """
    )
    for _, identifier, name in result:
        identifier = str(identifier)
        if identifier not in terms:
            logger.debug("isolated element in rdf: rhea:%s ! %s", identifier, name)
            continue
        terms[identifier].reference.name = name

    # TODO participants?

    yield from terms.values()


if __name__ == "__main__":
    RheaGetter.cli()
