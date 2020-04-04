# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import os
import urllib.error
from typing import Iterable

import click
import pandas as pd

from .sources import get_cbms2019_xrefs_df, get_gilda_xrefs_df
from ..extract import get_xrefs_df
from ..getters import MissingOboBuild
from ..path_utils import get_prefix_directory
from ..registries import get_metaregistry

SKIP = {
    'obi',
    'ncbigene',  # too big, refs axquired from  other dbs
    'pubchem.compound',  # to big, can't deal with this now
}
COLUMNS = ['source_ns', 'source_id', 'target_ns', 'target_id', 'source']


def get_xref_df() -> pd.DataFrame:
    """Get the ultimate xref databse."""
    df = pd.concat(_iterate_xref_dfs())
    df.sort_values(COLUMNS, inplace=True)
    return df


def _iterate_xref_dfs() -> Iterable[pd.DataFrame]:
    for prefix, _entry in _iterate_metaregistry():
        try:
            df = get_xrefs_df(prefix)
        except MissingOboBuild as e:
            click.secho(f'💾 {prefix}', bold=True)
            click.secho(str(e), fg='yellow')
            url = f'http://purl.obolibrary.org/obo/{prefix}.obo'
            click.secho(f'trying to query purl at {url}', fg='yellow')
            try:
                df = get_xrefs_df(prefix, url=url)
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

    yield get_gilda_xrefs_df()
    yield get_cbms2019_xrefs_df()


def _iterate_metaregistry():
    for prefix, _entry in sorted(get_metaregistry().items()):
        if prefix not in SKIP:
            yield prefix, _entry
