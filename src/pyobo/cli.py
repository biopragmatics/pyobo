# -*- coding: utf-8 -*-

import click


@click.command()
def main():
    import pickle
    from pyobo.sources.utils import get_terms_from_graph
    with open('/Users/cthoyt/.bio2bel/go/go-basic.obo.gpickle', 'rb') as file:
        g = pickle.load(file)

    terms = get_terms_from_graph(g)




if __name__ == '__main__':
    main()
