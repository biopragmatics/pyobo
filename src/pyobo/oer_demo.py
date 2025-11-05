"""Get all OER-related prefixes."""

import bioregistry
import click
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import pyobo


def main() -> None:
    """Get all OER-related prefixes."""
    collection = bioregistry.get_collection("0000018")
    if collection is None:
        raise ValueError
    for prefix in tqdm(collection.resources):
        tqdm.write(
            click.style(f"[{prefix}] {bioregistry.get_name(prefix, strict=True)}", fg="green")
        )
        with logging_redirect_tqdm():
            try:
                ontology = pyobo.get_ontology(prefix, cache=False, force_process=True, force=True)
            except Exception as e:
                tqdm.write(click.style(f"[{prefix}] failed\n\t{e}\n\n", fg="red"))
                continue
        terms = list(ontology)
        if not terms:
            tqdm.write(click.style(f"[{prefix}] failed, got no terms\n", fg="red"))
        else:
            tqdm.write(f"[{prefix}] got {len(terms):,} terms\n")


if __name__ == "__main__":
    main()
