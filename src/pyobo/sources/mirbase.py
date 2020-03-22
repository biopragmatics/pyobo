# -*- coding: utf-8 -*-

"""Converter for miRBase."""

import gzip
import logging
from typing import Iterable, List, Mapping

from tqdm import tqdm

from ..cache_utils import cached_mapping
from ..path_utils import ensure_df, ensure_path, prefix_directory_join
from ..struct import Obo, Reference, Synonym, Term, from_species
from ..struct.defs import has_mature

logger = logging.getLogger(__name__)

PREFIX = 'mirbase'
MIRBASE_MATURE_PREFIX = 'mirbase.mature'
VERSION = '22.1'
DEFINITIONS_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/miRNA.dat.gz'
ALIASES_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/aliases.txt.gz'
SPECIES_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/organisms.txt.gz'

xref_mapping = {
    'entrezgene': 'ncbigene',
}


def get_obo() -> Obo:
    """Get miRBase as OBO."""
    return Obo(
        ontology=PREFIX,
        name='miRBase',
        iter_terms=get_terms,
        typedefs=[from_species, has_mature],
        data_version=VERSION,
        auto_generated_by=f'bio2obo:{PREFIX}',
    )


def get_terms() -> List[Term]:
    """Parse miRNA data from filepath and convert it to dictionary."""
    definitions_path = ensure_path(PREFIX, DEFINITIONS_URL)

    file_handle = (
        gzip.open(definitions_path, 'rt')
        if definitions_path.endswith('.gz') else
        open(definitions_path)
    )
    with file_handle as file:
        return list(_process_definitions_lines(file))


def _prepare_organisms():
    df = ensure_df(PREFIX, SPECIES_URL, sep='\t', dtype={'#NCBI-taxid': str})
    return {
        division: (taxonomy_id, name)
        for _, division, name, _tree, taxonomy_id in df.values
    }


def _prepare_aliases() -> Mapping[str, List[str]]:
    df = ensure_df(PREFIX, ALIASES_URL, sep='\t')
    return {
        mirbase_id: [s.strip() for s in synonyms.split(';') if s and s.strip()]
        for mirbase_id, synonyms in df.values
    }


def _process_definitions_lines(lines: Iterable[str]) -> Iterable[Term]:
    """Process the lines of the definitions file."""
    organisms = _prepare_organisms()
    aliases = _prepare_aliases()

    groups = []

    for line in lines:  # TODO replace with itertools.groupby
        if line.startswith('ID'):
            listnew = []
            groups.append(listnew)
        groups[-1].append(line)

    for group in tqdm(groups, desc=f'mapping {PREFIX}'):
        name = group[0][5:23].strip()
        qualifier, dtype, species_code, length = map(str.strip, group[0][23:].strip().rstrip('.').split(';'))
        identifier = group[2][3:-2].strip()
        definition = group[4][3:-1].strip()

        synonyms = [
            Synonym(name=alias)
            for alias in aliases.get(identifier, [])
            if alias != name
        ]

        species_identifier, species_name = organisms[species_code]
        species = Reference(
            prefix='taxonomy',
            identifier=species_identifier,
            name=species_name,
        )

        mature_mirna_lines = [
            i
            for i, element in enumerate(group)
            if 'FT   miRNA    ' in element
        ]

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
            if product.endswith('3p') or product.endswith('5p'):
                matures.append(product_reference)
            else:
                pass
                # logger.warning(f'Whats going on {group[index]}')

        xrefs = []
        for line in group:
            if not line.startswith('DR'):
                continue
            line = line[len('DR   '):].strip().rstrip('.')
            xref_prefix, xref_identifier, xref_label = map(str.strip, line.split(';'))
            xref_prefix = xref_prefix.lower()
            xref_prefix = xref_mapping.get(xref_prefix, xref_prefix)
            xrefs.append(Reference(prefix=xref_prefix, identifier=xref_identifier,
                                   name=xref_label or None))

        # TODO add pubmed references

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
            xrefs=xrefs,
            synonyms=synonyms,
        )
        term.append_relationship(from_species, species)
        term.extend_relationship(has_mature, matures)

        yield term


@cached_mapping(
    path=prefix_directory_join(PREFIX, f'{PREFIX}.mature_to_{PREFIX}.tsv'),
    header=['mirbase.mature_id', 'mirbase_id'],
)
def get_mature_to_premature() -> Mapping[str, str]:
    """Get a mapping from mature miRNAs to their parents."""
    return {
        mature.identifier: term.identifier
        for term in get_terms()
        for mature in term.get_relationships(has_mature)
    }


@cached_mapping(
    path=prefix_directory_join(PREFIX, f'{PREFIX}.mature_mapping.tsv'),
    header=['mirbase.mature_id', 'name'],
)
def get_mature_id_to_name() -> Mapping[str, str]:
    """Get a mapping from mature miRNAs to their parents."""
    return {
        mature.identifier: mature.name
        for term in get_terms()
        for mature in term.get_relationships(has_mature)
    }


if __name__ == '__main__':
    get_obo().write_default()
