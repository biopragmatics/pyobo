# -*- coding: utf-8 -*-

"""CLI for the EdgeDB loader."""

import click

from .utils import test_connection
from ...registries import get_metaregistry
from ...sources import hgnc, mgi, rgd

insert_namespace = '''
    INSERT Namespace {
        prefix := <str>$prefix,
        name := <str>$name,
        pattern := <str>$pattern,
        namespace_in_pattern := <bool>$namespace_in_pattern,
    }
'''

insert_identifier = '''
    INSERT Identifier {
        reference := <str>$reference,
        namespace := (SELECT Namespace FILTER .prefix = <str>$namespace LIMIT 1)
    }
'''

insert_term = '''
    INSERT Term {
        reference := <str>$reference,
        namespace := (SELECT Namespace FILTER .prefix = <str>$namespace LIMIT 1)
    }
'''


@click.command()
def main():
    """Run a test upload."""
    # Establish a connection to an existing database
    # named "test" as an "edgedb" user.
    with test_connection() as conn:
        for namespace in get_metaregistry():
            conn.fetchall(
                insert_namespace,
                prefix=namespace['prefix'],
                name=namespace['name'],
                pattern=namespace['pattern'],
                namespace_in_pattern=namespace['namespace_in_pattern'],
            )

        obos = [
            hgnc.get_obo(), mgi.get_obo(), rgd.get_obo()
        ]
        for obo in obos:
            for term in obo.terms[:10]:
                conn.fetchall(
                    insert_identifier,
                    namespace=term.reference.prefix,
                    reference=term.reference.identifier,
                )

        # Select User objects.
        user_set = conn.fetchall('''
            SELECT Identifier {curie}
            FILTER .namespace.prefix = <str>$prefix
        ''', prefix='hgnc')
        print(user_set)


if __name__ == '__main__':
    main()
