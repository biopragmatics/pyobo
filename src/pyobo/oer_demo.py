"""Get all OER-related prefixes."""

import shutil

import bioregistry
import click
import pystow
from bioontologies.robot import ROBOTError
from more_click import verbose_option
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import pyobo
from pyobo.getters import NoBuildError

VALIDATED = {"ccso", "iana.mediatype"}
NEEDS_PYOBO = {
    "loc.fdd",  # see http://www.loc.gov/preservation/digital/formats/fddXML.zip
    "oerschema",  # see https://github.com/open-curriculum/oerschema/blob/master/src/config/schema.yml
}


# TODO add all vocabularies from https://vocabs.openeduhub.de/


@click.command()
@click.option("-r", "--refresh", is_flag=True)
@verbose_option
def main(refresh: bool = False) -> None:
    """Get all OER-related prefixes."""
    collection = bioregistry.get_collection("0000018")
    if collection is None:
        raise ValueError

    prefixes = [p for p in collection.resources if p not in VALIDATED and p not in NEEDS_PYOBO]
    if refresh:
        for prefix in tqdm(prefixes):
            directory = pystow.join("pyobo", "raw", prefix)
            if directory.is_dir():
                shutil.rmtree(directory)
        return

    for prefix in tqdm(prefixes, disable=True):
        tqdm.write(
            click.style(f"[{prefix}] {bioregistry.get_name(prefix, strict=True)}", fg="green")
        )
        with logging_redirect_tqdm():
            try:
                ontology = pyobo.get_ontology(prefix, cache=False, force_process=True, force=False)
            except NotImplementedError as e:
                tqdm.write(click.style(f"[{prefix}] failed because not implemented: {e}", fg="red"))
                continue
            except NoBuildError:
                tqdm.write(click.style(f"[{prefix}] no build", fg="yellow"))
                continue
            except ROBOTError as e:
                tqdm.write(click.style(f"[{prefix}]\n{e}", fg="yellow"))
                continue
            except Exception as e:
                tqdm.write(click.style(f"[{prefix}] failed\n\t{e}\n\n", fg="red"))
                raise
        terms = list(ontology)
        if not terms:
            tqdm.write(click.style(f"[{prefix}] failed, got no terms\n", fg="red"))
        else:
            tqdm.write(f"[{prefix}] got {len(terms):,} terms\n")


if __name__ == "__main__":
    main()
