# -*- coding: utf-8 -*-

"""Uploader for OBO."""

import click
from tqdm import tqdm

from pyobo.database.sql.manager import Manager
from pyobo.database.sql.models import Reference, Term
from pyobo.sources.utils import get_terms_from_graph
from pyobo.utils import get_obo_graph


@click.command()
def main():
    """Upload pickle graph."""
    g = get_obo_graph('go')
    terms = get_terms_from_graph(g)

    references = {}

    manager = Manager()
    manager.create_all()

    for term in tqdm(terms[:500]):
        reference = references.get(term.reference.curie)
        if reference is None:
            reference = references[term.reference.curie] = Reference(
                namespace=term.reference.namespace,
                identifier=term.reference.identifier,
                name=term.reference.name
            )

        term = Term(
            reference=reference,
            definition=term.definition,
        )

        manager.session.add(term)

    manager.session.commit()


if __name__ == '__main__':
    main()
