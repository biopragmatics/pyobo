# -*- coding: utf-8 -*-

"""Extract *all* xrefs from OBO documents available."""

import os
import urllib.error
from typing import Iterable

import click
import pandas as pd

from .extract_xrefs import UNHANDLED_NAMESPACES, get_all_xrefs
from ..cli_utils import verbose_option
from ..getters import MissingOboBuild
from ..path_utils import get_prefix_directory
from ..registries import get_metaregistry

#: Keys are prefixes and values point to OBO URLs to download
# OBO = {
#     # High quality
#     'hp': 'http://purl.obolibrary.org/obo/hp.obo',
#     "chebi": "http://purl.obolibrary.org/obo/chebi.obo",
#
#     'doid': 'http://purl.obolibrary.org/obo/doid.obo',
#     'efo': 'http://www.ebi.ac.uk/efo/efo.obo',
#     "go": "http://purl.obolibrary.org/obo/go.obo",
#     "obi": "http://purl.obolibrary.org/obo/obi.obo",
#     # Others
#     "pr": "http://purl.obolibrary.org/obo/pr.obo",
#     "bto": "http://purl.obolibrary.org/obo/bto.obo",
#     "cl": "http://purl.obolibrary.org/obo/cl.obo",
#     # "clo":  # not distributed as OBO
#     "cmo": "http://purl.obolibrary.org/obo/cmo.obo",
#     "ecto": "http://purl.obolibrary.org/obo/ecto.obo",
#     "exo": "http://purl.obolibrary.org/obo/exo.obo",
#     "fbbt": "http://purl.obolibrary.org/obo/fbbt.obo",
#     'mondo': 'http://purl.obolibrary.org/obo/mondo.obo',
#     "mp": "http://purl.obolibrary.org/obo/mp.obo",
#
#     'ncit': 'http://purl.obolibrary.org/obo/ncit.obo',
#     "pato": "http://purl.obolibrary.org/obo/pato.obo",
#     "peco": "http://purl.obolibrary.org/obo/peco.obo",
#     "pw": "http://purl.obolibrary.org/obo/pw.obo",
#     'symp': 'http://purl.obolibrary.org/obo/symp.obo',
#     "to": "http://purl.obolibrary.org/obo/to.obo",
# }

SKIP = {
    'obi',
    'ncbigene',  # too big, refs axquired from  other dbs
    'pubchem.compound',  # to big, can't deal with this now
}

columns = ['source_ns', 'source_id', 'target_ns', 'target_id', 'source']


def _iterate_xref_dfs() -> Iterable[pd.DataFrame]:
    for prefix, _entry in sorted(get_metaregistry().items()):
        if prefix in SKIP:
            continue

        try:
            df = get_all_xrefs(prefix)
        except MissingOboBuild as e:
            click.secho(f'💾 {prefix}', bold=True)
            click.secho(str(e), fg='yellow')
            url = f'http://purl.obolibrary.org/obo/{prefix}.obo'
            click.secho(f'trying to query purl at {url}', fg='yellow')
            try:
                df = get_all_xrefs(prefix, url=url)
                click.secho(f'resolved {prefix} with {url}', fg='green')
            except Exception as e2:
                click.secho(str(e2), fg='yellow')
                continue
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            click.secho(f'💾 {prefix}', bold=True)
            click.secho(f'Bad URL for {prefix}')
            click.secho(str(e))
            continue
        except ValueError:
            # click.secho(f'Not in available as OBO through OBO Foundry or PyOBO: {prefix}', fg='yellow')
            continue

        df['source'] = prefix
        df.drop_duplicates(inplace=True)
        yield df

        prefix_directory = get_prefix_directory(prefix)
        if not os.listdir(prefix_directory):
            os.rmdir(prefix_directory)


@click.command()
@click.option('--directory', type=click.Path(dir_okay=True, file_okay=False, exists=True), default=os.getcwd())
@verbose_option
def cache_xrefs(directory):  # noqa: D202
    """Output the mappings."""

    def _write_tsv(df: pd.DataFrame, name: str) -> None:
        df.to_csv(os.path.join(directory, name), sep='\t', index=False)

    xrefs_df = pd.concat(_iterate_xref_dfs())
    xrefs_df.sort_values(columns, inplace=True)

    # Export all xrefs
    _write_tsv(xrefs_df, f'xrefs.tsv')
    _write_tsv(xrefs_df, f'xrefs.tsv.gz')

    # Export a sample of xrefs
    _write_tsv(xrefs_df.head(), f'xrefs_sample.tsv')

    # Export a summary dataframe
    summary_df = xrefs_df.groupby(['source', 'target_ns'])['source_ns'].count().reset_index()
    summary_df = summary_df.sort_values(['source_ns'], ascending=False)
    _write_tsv(summary_df, 'summary.tsv')

    # Export the namespaces that haven't been handled yet
    unmapped_path = os.path.join(directory, 'unmapped.tsv')
    with open(unmapped_path, 'w') as file:
        for namespace, items in sorted(UNHANDLED_NAMESPACES.items()):
            for curie, xref in items:
                print(curie, namespace, xref, file=file, sep='\t')


if __name__ == '__main__':
    cache_xrefs()
