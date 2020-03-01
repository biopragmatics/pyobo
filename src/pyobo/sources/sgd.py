from urllib.parse import unquote_plus

import pandas as pd

from pyobo import Obo, Reference, Synonym, SynonymTypeDef, Term
from pyobo.sources.utils import from_species

HEADER = ['chromosome', 'database', 'feature', 'start', 'end', 'a', 'b', 'c', 'data']
PREFIX = 'sgd'

path = '/Users/cthoyt/Downloads/S288C_reference_genome_R64-2-1_20150113/saccharomyces_cerevisiae_R64-2-1_20150113.gff'

alias_type = SynonymTypeDef(id='alias', name='alias')


def get_obo() -> Obo:
    terms = list(get_rows(path))
    return Obo(
        ontology=PREFIX,
        terms=terms,
        synonym_typedefs=[alias_type],
    )


def get_rows(path):
    df = pd.read_csv(path, sep='\t', skiprows=18, header=None, names=HEADER)
    df = df[df['feature'] == 'gene']
    for data in df['data']:
        d = dict(entry.split('=') for entry in data.split(';'))

        identifier = d['dbxref'][len('SGD:'):]
        name = d['Name']
        definition = unquote_plus(d['Note'])

        synonyms = []

        aliases = d.get('Alias')
        if aliases:
            for alias in aliases.split(','):
                synonyms.append(Synonym(name=unquote_plus(alias), type=alias_type))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier),
            name=name,
            definition=definition,
            synonyms=synonyms,
        )
        term.append_relationship(
            from_species,
            Reference(prefix='taxonomy', identifier='4932', label='Saccharomyces cerevisiae'),
        )
        yield term


if __name__ == '__main__':
    get_obo().write_default()
