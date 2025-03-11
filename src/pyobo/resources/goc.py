"""Get GOC to ORCID CURIE mappings.

Due to historical reasons, the Gene Ontology and related resources use an internal
curator identifier space ``GOC`` instead of ORCID. This namespace is partially mapped to
ORCID and is version controlled `here
<https://raw.githubusercontent.com/geneontology/go-site/refs/heads/master/metadata/users.yaml>`_.

This module loads that namespace and uses :mod:`orcid_downloader` to try and add
additional ORCID groundings. Then, this module is loaded in PyOBO's custom CURIE upgrade
system so GOC CURIEs are seamlessly replaced with ORCID CURIEs, when possible.

.. seealso::

    https://github.com/geneontology/go-ontology/issues/22551
"""

import csv
from pathlib import Path

__all__ = ["load_goc_map"]

URL = "https://raw.githubusercontent.com/geneontology/go-site/refs/heads/master/metadata/users.yaml"

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("goc.tsv")


def load_goc_map() -> dict[str, str]:
    """Get GOC to ORCID mappings."""
    rv = {}
    with PATH.open() as f:
        for goc_curie, _, orcid, *_ in csv.reader(f, delimiter="\t"):
            rv[goc_curie] = f"orcid:{orcid}"
            rv[goc_curie.upper()] = f"orcid:{orcid}"
    return rv


def main() -> None:
    """Generate GOC to ORCID mappings."""
    import orcid_downloader
    import requests
    import yaml
    from tqdm import tqdm

    columns = ["curie", "name", "orcid", "guessed"]
    res = requests.get(URL, timeout=5)
    records = yaml.safe_load(res.text)
    with PATH.open("w") as file:
        print(*columns, sep="\t", file=file)
        for record in tqdm(records, unit="person"):
            goc_curie = record.get("xref")
            if goc_curie is None or not goc_curie.startswith("GOC:"):
                continue

            guessed = False
            nickname = record["nickname"]
            uri = record.get("uri", "")
            if not uri:
                continue
            if "orcid.org" in uri:
                orcid = uri.removeprefix("https://orcid.org/").removeprefix("https://orcid.org/")
            if "orcid.org" not in uri:
                orcid = orcid_downloader.ground_researcher_unambiguous(nickname)
                if not orcid:
                    tqdm.write(f"Could not guess ORCID for {nickname}")
                    continue

                tqdm.write(f"Check if https://orcid.org/{orcid} is correct for {nickname}")
                guessed = True

            print(goc_curie, nickname, orcid, guessed, sep="\t", file=file)


if __name__ == "__main__":
    main()
