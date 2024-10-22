"""Converter for UniProt PTMs.

Line code  Content                         Occurrence in an entry
---------  ---------------------------     ------------------------------
ID         Identifier (FT description)     Once; starts a PTM entry
AC         Accession (PTM-xxxx)            Once
FT         Feature key                     Once
TG         Target                          Once; two targets separated by
                                           a dash in case of intrachain
                                           crosslinks
PA         Position of the modification    Optional; once
           on the amino acid
PP         Position of the modification    Optional; once
           in the polypeptide
CF         Correction formula              Optional; once
MM         Monoisotopic mass difference    Optional; once
MA         Average mass difference         Optional; once
LC         Cellular location               Optional; once; alternatives
                                           can be proposed
TR         Taxonomic range                 Optional; once or more
KW         Keyword                         Optional; once or more
DR         Cross-reference to external     Optional; once or more
           databases
//         Terminator                      Once; ends an entr

"""

import itertools as itt
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Optional

from tqdm.auto import tqdm

from pyobo import Obo, Reference, Term
from pyobo.utils.path import ensure_path

__all__ = [
    "UniProtPtmGetter",
]

PREFIX = "uniprot.ptm"
URL = "https://www.uniprot.org/docs/ptmlist.txt"


class UniProtPtmGetter(Obo):
    """An ontology representation of the UniProt PTM database."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield from iter_terms(force=force)


def get_obo(force: bool = False) -> Obo:
    """Get UniProt PTMs as OBO."""
    return UniProtPtmGetter(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over UniProt PTM Terms."""
    path = ensure_path(PREFIX, url=URL, force=force)
    with open(path) as file:
        lines = list(file)
    it: Iterable[tuple[str, str]] = ((line[:2], line[2:].strip()) for line in lines[47:-5])
    for i, (_, term_lines) in enumerate(itt.groupby(it, key=lambda p: p[0] == "//")):
        term = _parse(i, term_lines)
        if term:
            yield term


def _parse(i, lines: Iterable[tuple[str, str]]) -> Optional[Term]:
    dd_: defaultdict[str, list[str]] = defaultdict(list)
    for key, value in lines:
        dd_[key].append(value)
    dd: Mapping[str, list[str]] = dict(dd_)

    if "//" in dd:
        return None

    accessions = dd["AC"]
    labels = dd.get("ID")
    reference = Reference(
        prefix="uniprot.ptm",
        identifier=accessions[0],
        name=labels[0] if labels else None,
    )
    term = Term(reference=reference)
    for line in dd.get("DR", []):
        line = line.rstrip(".")
        for x, y in [
            ("MOD; ", "PSI-MOD; MOD:"),
            ("CHEBI; ", "ChEBI; CHEBI:"),
        ]:
            if line.startswith(y):
                line = x + line[len(y) :]

        ref = Reference.from_curie(line.replace("; ", ":"))
        if ref:
            term.append_xref(ref)
        else:
            tqdm.write(f"Failure on xref {line}")
    return term


if __name__ == "__main__":
    UniProtPtmGetter.cli()
