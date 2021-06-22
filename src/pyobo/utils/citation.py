# -*- coding: utf-8 -*-

"""Normalization of citation URLs."""

from typing import Tuple, Union

import click

__all__ = [
    "normalize_citation",
]

RAW_DOI_PREFIXES = {
    "10.21203/",
    "10.26434/",
    "10.20944/",
}

PREFIXES = {
    "https://doi.org/": "doi",
    "http://biorxiv.org/lookup/doi/": "biorxiv",
    "http://medrxiv.org/lookup/doi/": "medrxiv",
    "http://jvi.asm.org/cgi/doi/": "doi",
    "https://www.sciencemag.org/lookup/doi/": "doi",
    "http://doi.wiley.com/": "doi",
    "https://onlinelibrary.wiley.com/doi/full/": "doi",
    "http://bmcsystbiol.biomedcentral.com/articles/": "doi",
    "https://dx.plos.org/": "doi",
    "http://www.nejm.org/doi/": "doi",
    "https://onlinelibrary.wiley.com/doi/abs/": "doi",
    "http://www.pnas.org/cgi/doi/": "doi",
    "https://www.microbiologyresearch.org/content/journal/jgv/": "doi",
    "http://link.springer.com/": "doi",
    "http://jcm.asm.org/lookup/doi/": "doi",
    "https://www.tandfonline.com/doi/": "doi",
    "https://www.annualreviews.org/doi/": "doi",
}


def normalize_citation(line: str) -> Union[Tuple[str, str], Tuple[None, str]]:
    """Normalize a citation string that might be a crazy URL from a publisher."""
    if line.isalnum():
        return "pubmed", line

    for prefix in RAW_DOI_PREFIXES:
        if line.startswith(prefix):
            for v in range(10):
                if line.endswith(f".v{v}"):
                    line = line[: -len(f".v{v}")]
            return "doi", line

    for prefix, ns in PREFIXES.items():
        if line.startswith(prefix):
            return ns, line[len(prefix) :]

    if line.startswith("https://www.ncbi.nlm.nih.gov/pmc/articles/"):
        line = line[len("https://www.ncbi.nlm.nih.gov/pmc/articles/") :]
        line = line.rstrip("/")
        return "pmc", line

    if line.startswith("https://www.biorxiv.org/content/"):
        line = line[len("https://www.biorxiv.org/content/") :].rstrip()
        if line.endswith(".pdf"):
            line = line[: -len(".pdf")]
        if line.endswith(".full"):
            line = line[: -len(".full")]
        for v in range(10):
            if line.endswith(f"v{v}"):
                line = line[: -len(f"v{v}")]
        return "doi", line

    if line.startswith("https://www.preprints.org/manuscript/"):
        line = line[len("https://www.preprints.org/manuscript/") :]
        for v in range(10):
            if line.endswith(f"/v{v}"):
                line = line[: -len(f"/v{v}")]
        return "doi", f"10.20944/preprints{line}"

    if line.startswith("https://www.frontiersin.org/article/"):
        line = line[len("https://www.frontiersin.org/article/") :]
        if line.endswith("/full"):
            line = line[: -len("/full")]
        return "doi", line

    return None, line


@click.command()
@click.option("-f", "--file", type=click.File())
def main(file):
    """Normalize a file with random citations."""
    for line in file:
        line = line.strip()
        prefix, identifier = normalize_citation(line)
        if not prefix or not identifier:
            click.echo(f"unnormalized: {line}")
        else:
            click.echo(f"{prefix}\t{identifier}")


if __name__ == "__main__":
    main()
