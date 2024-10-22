"""CLI for PyOBO's interface to S3."""

import click
from more_click import verbose_option

from ..aws import download_artifacts, list_artifacts, upload_artifacts

__all__ = [
    "main",
]

bucket_argument = click.argument("bucket")


@click.group(name="aws")
def main():
    """S3 utilities."""


@main.command()
@bucket_argument
@verbose_option
def download(bucket):
    """Download all artifacts from the S3 bucket."""
    download_artifacts(bucket)


@main.command()
@bucket_argument
@verbose_option
@click.option("-w", "--whitelist", multiple=True)
@click.option("-b", "--blacklist", multiple=True)
def upload(bucket, whitelist, blacklist):
    """Download all artifacts from the S3 bucket."""
    upload_artifacts(bucket, whitelist=whitelist, blacklist=blacklist)


@main.command()
@bucket_argument
@verbose_option
def ls(bucket):
    """List all artifacts on the S3 bucket."""
    click.echo(list_artifacts(bucket))


if __name__ == "__main__":
    main()
