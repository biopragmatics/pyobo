# -*- coding: utf-8 -*-

"""Converter for miRBase."""

import gzip
import logging
from typing import Iterable, List, Mapping

import bioversions
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, Term, from_species
from ..struct.typedef import has_mature
from ..utils.cache import cached_mapping
from ..utils.path import ensure_df, ensure_path, prefix_directory_join

logger = logging.getLogger(__name__)

PREFIX = "mirbase"
MIRBASE_MATURE_PREFIX = "mirbase.mature"

xref_mapping = {
    "entrezgene": "ncbigene",
    "targets:pictar-vert": "pictar",
    "targets:mirte": "mirte",
    "targets:pictar-fly": "pictar",
}


def get_obo() -> Obo:
    """Get miRBase as OBO."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name="miRBase",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(version=version),
        typedefs=[from_species, has_mature],
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_terms(version: str) -> List[Term]:
    """Parse miRNA data from filepath and convert it to dictionary."""
    url = f"ftp://mirbase.org/pub/mirbase/{version}/miRNA.dat.gz"
    definitions_path = ensure_path(PREFIX, url=url, version=version)

    file_handle = (
        gzip.open(definitions_path, "rt")
        if definitions_path.endswith(".gz")
        else open(definitions_path)
    )
    with file_handle as file:
        return list(_process_definitions_lines(file, version=version))


def _prepare_organisms(version: str):
    url = f"ftp://mirbase.org/pub/mirbase/{version}/organisms.txt.gz"
    df = ensure_df(PREFIX, url=url, sep="\t", dtype={"#NCBI-taxid": str}, version=version)
    return {division: (taxonomy_id, name) for _, division, name, _tree, taxonomy_id in df.values}


def _prepare_aliases(version: str) -> Mapping[str, List[str]]:
    url = f"ftp://mirbase.org/pub/mirbase/{version}/aliases.txt.gz"
    df = ensure_df(PREFIX, url=url, sep="\t", version=version)
    return {
        mirbase_id: [s.strip() for s in synonyms.split(";") if s and s.strip()]
        for mirbase_id, synonyms in df.values
    }


def _process_definitions_lines(lines: Iterable[str], version: str) -> Iterable[Term]:
    """Process the lines of the definitions file."""
    organisms = _prepare_organisms(version)
    aliases = _prepare_aliases(version)

    groups = []

    for line in lines:  # TODO replace with itertools.groupby
        if line.startswith("ID"):
            listnew = []
            groups.append(listnew)
        groups[-1].append(line)

    for group in tqdm(groups, desc=f"mapping {PREFIX}"):
        name = group[0][5:23].strip()
        qualifier, dtype, species_code, length = map(
            str.strip, group[0][23:].strip().rstrip(".").split(";")
        )
        identifier = group[2][3:-2].strip()
        definition = group[4][3:-1].strip()

        synonyms = [Synonym(name=alias) for alias in aliases.get(identifier, []) if alias != name]
        mature_mirna_lines = [i for i, element in enumerate(group) if "FT   miRNA    " in element]

        matures = []
        for index in mature_mirna_lines:
            # location = group[index][10:-1].strip()
            accession = group[index + 1][33:-2]
            product = group[index + 2][31:-2]
            product_reference = Reference(
                prefix=MIRBASE_MATURE_PREFIX,
                identifier=accession,
                name=product,
            )
            if product.endswith("3p") or product.endswith("5p"):
                matures.append(product_reference)
            else:
                pass
                # logger.warning(f'Whats going on {group[index]}')

        xrefs = []
        for line in group:
            if not line.startswith("DR"):
                continue
            line = line[len("DR   ") :].strip().rstrip(".")
            xref_prefix, xref_identifier, xref_label = map(str.strip, line.split(";"))
            xref_prefix = xref_prefix.lower()
            xref_prefix = xref_mapping.get(xref_prefix, xref_prefix)
            xrefs.append(
                Reference(prefix=xref_prefix, identifier=xref_identifier, name=xref_label or None)
            )

        # TODO add pubmed references

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
            xrefs=xrefs,
            synonyms=synonyms,
        )

        species_identifier, species_name = organisms[species_code]
        term.set_species(species_identifier, species_name)
        term.extend_relationship(has_mature, matures)

        yield term


def get_mature_to_premature(version: str) -> Mapping[str, str]:
    """Get a mapping from mature miRNAs to their parents."""

    @cached_mapping(
        path=prefix_directory_join(
            PREFIX, name=f"{PREFIX}.mature_to_{PREFIX}.tsv", version=version
        ),
        header=["mirbase.mature_id", "mirbase_id"],
    )
    def _inner():
        return {
            mature.identifier: term.identifier
            for term in get_terms(version)
            for mature in term.get_relationships(has_mature)
        }

    return _inner()


def get_mature_id_to_name(version: str) -> Mapping[str, str]:
    """Get a mapping from mature miRNAs to their parents."""

    @cached_mapping(
        path=prefix_directory_join(PREFIX, name=f"{PREFIX}.mature_mapping.tsv", version=version),
        header=["mirbase.mature_id", "name"],
    )
    def _inner():
        return {
            mature.identifier: mature.name
            for term in get_terms(version)
            for mature in term.get_relationships(has_mature)
        }

    return _inner()


if __name__ == "__main__":
    get_obo().write_default()
