# -*- coding: utf-8 -*-

"""CLI for PyOBO Database Generation."""

import os

import click
from more_click import verbose_option
from zenodo_client import update_zenodo

from .utils import directory_option, force_option, no_strict_option, zenodo_option
from ..getters import db_output_helper
from ..xrefdb.xrefs_pipeline import (
    _iter_alts, _iter_ooh_na_na, _iter_synonyms, get_xref_df, summarize_xref_df,
    summarize_xref_provenances_df,
)

__all__ = [
    'main',
]


@click.group(name='database')
def main():
    """Build the PyOBO Database."""


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
@click.pass_context
def build(ctx: click.Context, directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Build all databases."""
    click.secho('Alternate Identifiers', fg='cyan', bold=True)
    ctx.invoke(alts, directory=directory, zenodo=zenodo, no_strict=no_strict, force=force)  # only need to force once
    click.secho('Synonyms', fg='cyan', bold=True)
    ctx.invoke(synonyms, directory=directory, zenodo=zenodo)
    click.secho('Xrefs', fg='cyan', bold=True)
    ctx.invoke(xrefs, directory=directory, zenodo=zenodo)
    click.secho('Names', fg='cyan', bold=True)
    ctx.invoke(names, directory=directory, zenodo=zenodo)
    # TODO relations
    # TODO properties


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def names(directory: str, zenodo: bool, no_strict: bool, force: bool):
    """Make the prefix-identifier-name dump."""
    paths = db_output_helper(
        _iter_ooh_na_na,
        'names',
        ('prefix', 'identifier', 'name'),
        strict=not no_strict,
        force=force,
        directory=directory,
    )
    if zenodo:
        # see https://zenodo.org/record/4020486
        update_zenodo('4020486', paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def alts(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the prefix-alt-id dump."""
    paths = db_output_helper(
        _iter_alts, 'alts', ('prefix', 'identifier', 'alt'),
        directory=directory,
        force=force,
        strict=not no_strict,
    )
    if zenodo:
        # see https://zenodo.org/record/4021476
        update_zenodo('4021476', paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def synonyms(directory: str, zenodo: bool, force: bool, no_strict: bool):
    """Make the prefix-identifier-synonym dump."""
    paths = db_output_helper(
        _iter_synonyms, 'synonyms', ('prefix', 'identifier', 'synonym'),
        directory=directory,
        force=force,
        strict=not no_strict,
    )
    if zenodo:
        # see https://zenodo.org/record/4021482
        update_zenodo('4021482', paths)


@main.command()
@verbose_option
@directory_option
@zenodo_option
@force_option
@no_strict_option
def xrefs(directory: str, zenodo: bool, force: bool, no_strict: bool):  # noqa: D202
    """Make the prefix-identifier-xref dump."""
    # Export all xrefs
    xrefs_df = get_xref_df(rebuild=True, force=force, strict=not no_strict)
    xrefs_path = os.path.join(directory, 'xrefs.tsv.gz')
    xrefs_df.to_csv(xrefs_path, sep='\t', index=False)

    # Export a sample of xrefs
    sample_path = os.path.join(directory, 'xrefs_sample.tsv')
    xrefs_df.head().to_csv(sample_path, sep='\t', index=False)

    # Export a summary dataframe
    summary_df = summarize_xref_df(xrefs_df)
    summary_path = os.path.join(directory, 'xrefs_summary.tsv')
    summary_df.to_csv(summary_path, sep='\t', index=False)

    summary_provenances_df = summarize_xref_provenances_df(xrefs_df)
    summary_provenances_path = os.path.join(directory, 'xrefs_summary_provenance.tsv')
    summary_provenances_df.to_csv(summary_provenances_path, sep='\t', index=False)

    if zenodo:
        # see https://zenodo.org/record/4021477
        update_zenodo('4021477', [xrefs_path, sample_path, summary_path, summary_provenances_path])


if __name__ == '__main__':
    main()
