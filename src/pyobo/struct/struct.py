# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, TextIO, Union

import networkx as nx
from networkx.utils import open_file

from .registry import Registry, miriam
from .utils import comma_separate, obo_escape
from ..path_utils import get_prefix_obo_path

__all__ = [
    'Reference',
    'Synonym',
    'SynonymTypeDef',
    'TypeDef',
    'Term',
    'Obo',
]


@dataclass
class Reference:
    """A namespace, identifier, and label."""

    #: The namespace's keyword
    prefix: str

    #: The entity's identifier in the namespace
    identifier: str

    name: Optional[str] = field(default=None, repr=None)

    #: The namespace's identifier in the registry
    registry_id: Optional[str] = field(default=None, repr=False)

    #: The registry in which the namespace can be looked up
    registry: Registry = field(default=miriam, repr=False)

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this reference."""
        return f'{self.prefix}:{self.identifier}'

    @staticmethod
    def from_curie(curie: str) -> Reference:
        """Get a reference from a CURIE."""
        prefix, identifier = curie.strip().split(':')
        return Reference(prefix=prefix.lower(), identifier=identifier)

    @staticmethod
    def from_curies(curies: str) -> List[Reference]:
        """Get a list of references from a string with comma separated CURIEs."""
        return [
            Reference.from_curie(curie)
            for curie in curies.split(',')
            if curie.strip()
        ]

    @staticmethod
    def default(identifier, name) -> Reference:
        """Return a reference from the PyOBO namespace."""
        return Reference(prefix='obo', identifier=identifier, name=name)

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def __str__(self):  # noqa: D105
        if self.identifier.lower().startswith(f'{self.prefix.lower()}:'):
            rv = self.identifier.lower()
        else:
            rv = f'{self.prefix}:{self._escaped_identifier}'
        if self.name:
            rv = f'{rv} ! {self.name}'
        return rv

    def __hash__(self):  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: str = 'EXACT'

    #: The type of synonym. Must be defined in OBO document!
    type: Optional[SynonymTypeDef] = None

    #: References to articles where the synonym appears
    provenance: List[Reference] = field(default_factory=list)

    def to_obo(self) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f'synonym: {self._fp()}'

    def _fp(self) -> str:
        x = f'"{self.name}" {self.specificity}'
        if self.type:
            x = f'{x} {self.type.id}'
        return f'{x} [{comma_separate(self.provenance)}]'


@dataclass
class SynonymTypeDef:
    """A type definition for synonyms in OBO."""

    id: str
    name: str

    def to_obo(self) -> str:
        """Serialize to OBO."""
        return f'synonymtypedef: {self.id} "{self.name}"'


class _Referenced:
    """A class that contains a reference."""

    reference: Reference

    @property
    def prefix(self):  # noqa: D401
        """The prefix of the typedef."""
        return self.reference.prefix

    @property
    def name(self):  # noqa: D401
        """The name of the typedef."""
        return self.reference.name

    @property
    def identifier(self) -> str:  # noqa: D401
        """The local unique identifier for this typedef."""
        return self.reference.identifier

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this typedef."""
        return self.reference.curie


@dataclass
class TypeDef(_Referenced):
    """A type definition in OBO."""

    reference: Reference
    comment: Optional[str] = None
    namespace: Optional[str] = None
    definition: Optional[str] = None
    is_transitive: Optional[bool] = None
    domain: Optional[Reference] = None
    range: Optional[Reference] = None
    parents: List[Reference] = field(default_factory=list)
    xrefs: List[Reference] = field(default_factory=list)
    inverse: Optional[Reference] = None

    def __hash__(self) -> int:  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield '\n[Typedef]'
        yield f'id: {self.reference.curie}'
        yield f'name: {self.reference.name}'

        if self.namespace:
            yield f'namespace: {self.namespace}'

        if self.comment:
            yield f'comment: {self.comment}'

        for xref in self.xrefs:
            yield f'xref: {xref}'

        if self.is_transitive is not None:
            yield f'is_transitive: {"true" if self.is_transitive else "false"}'


@dataclass
class Term(_Referenced):
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: Optional[str] = None

    #: References to articles in which the term appears
    provenance: List[Reference] = field(default_factory=list)

    #: Relationships defined by [Typedef] stanzas
    relationships: Dict[TypeDef, List[Reference]] = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: List[Reference] = field(default_factory=list)

    #: Synonyms of this term
    synonyms: List[Synonym] = field(default_factory=list)

    #: Equivalent references
    xrefs: List[Reference] = field(default_factory=list)

    #: The sub-namespace within the ontology
    namespace: Optional[str] = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: Optional[bool] = None

    def get_relationships(self, type_def: TypeDef) -> List[Reference]:
        """Get relationships from the given type."""
        return self.relationships[type_def]

    def append_relationship(self, type_def: TypeDef, reference: Reference) -> None:
        """Append a relationship."""
        self.relationships[type_def].append(reference)

    def extend_relationship(self, type_def: TypeDef, references: Iterable[Reference]) -> None:
        """Append several relationships."""
        self.relationships[type_def].extend(references)

    def _definition_fp(self):
        return f'"{self.definition}" [{comma_separate(self.provenance)}]'

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield '\n[Term]'
        yield f'id: {self.curie}'
        yield f'name: {self.name}'
        if self.namespace and self.namespace != '?':
            namespace_normalized = self.namespace \
                .replace(' ', '_') \
                .replace('-', '_') \
                .replace('(', '') \
                .replace(')', '')
            yield f'namespace: {namespace_normalized}'

        if self.definition:
            yield f'def: {self._definition_fp()}'

        for xref in sorted(self.xrefs, key=attrgetter('prefix', 'identifier')):
            yield f'xref: {xref}'

        for parent in sorted(self.parents, key=attrgetter('prefix', 'identifier')):
            yield f'is_a: {parent}'

        for type_def, references in sorted(self.relationships.items(), key=lambda x: x[0].name):
            for reference in references:
                s = f'relationship: {type_def.curie} {reference.curie}'
                # Obonet doesn't support this. re-enable later.
                # if type_def.name or reference.name:
                #     s += ' !'
                # if type_def.name:
                #     s += f' {type_def.name}'
                # if reference.name:
                #     s += f' {reference.name}'
                yield s

        for synonym in sorted(self.synonyms, key=attrgetter('name')):
            yield synonym.to_obo()


@dataclass
class Obo:
    """An OBO document."""

    #: The prefix for the ontology
    ontology: str

    #: The name of the ontology
    name: str

    #: A function that iterates over terms
    iter_terms: Callable[[], Iterable[Term]]

    #: The OBO format
    format_version: str = '1.2'

    #: Type definitions
    typedefs: List[TypeDef] = field(default_factory=list)

    #: Synonym type definitions
    synonym_typedefs: List[SynonymTypeDef] = field(default_factory=list)

    #: Regular expression pattern describing the local unique identifiers
    pattern: Optional[str] = None

    #: Is the prefix at the begging of each local unique identifier
    namespace_in_pattern: Optional[bool] = None

    #: The ontology version
    data_version: Optional[str] = None

    #: An annotation about how an ontology was generated
    auto_generated_by: Optional[str] = None

    #: The date the ontology was generated
    date: datetime = field(default_factory=datetime.today)

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return self.date.strftime("%d:%m:%Y %H:%M")

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f'format-version: {self.format_version}'
        yield f'date: {self.date_formatted}'

        if self.auto_generated_by is not None:
            yield f'auto-generated-by: {self.auto_generated_by}'

        if self.data_version is not None:
            yield f'data-version: {self.data_version}'

        for synonym_typedef in sorted(self.synonym_typedefs, key=attrgetter('id')):
            yield synonym_typedef.to_obo()

        yield f'ontology: {self.ontology}'

        for typedef in self.typedefs:
            yield from typedef.iterate_obo_lines()

        for term in self.iter_terms():
            yield from term.iterate_obo_lines()

    @open_file(1, mode='w')
    def write(self, file: Union[None, str, TextIO, Path] = None) -> None:
        """Write the OBO to a file."""
        for line in self.iterate_obo_lines():
            print(line, file=file)

    def write_obonet_gz(self, path: str) -> None:
        """Write the OBO to a gzipped dump in Obonet JSON."""
        graph = self.to_obonet()
        with gzip.open(path, 'wt') as file:
            json.dump(nx.node_link_data(graph), file)

    def write_default(self) -> None:
        """Write the OBO to the default path."""
        path = get_prefix_obo_path(self.ontology)
        self.write(path)

    def __iter__(self):  # noqa: D105
        return iter(self.iter_terms())

    def to_obonet(self: Obo) -> nx.MultiDiGraph:
        """Export as a :mod`obonet` style graph."""
        rv = nx.MultiDiGraph()
        rv.graph.update({
            'name': self.name,
            'ontology': self.ontology,
            'auto-generated-by': self.auto_generated_by,
            'typedefs': _convert_type_defs(self.typedefs),
            'format_version': self.format_version,
            'synonymtypedef': _convert_synonym_type_defs(self.synonym_typedefs),
            'date': self.date_formatted,
        })

        nodes = {}
        links = []
        for term in self.iter_terms():
            parents = []
            for parent in term.parents:
                links.append((term.curie, 'is_a', parent.curie))
                parents.append(parent.curie)

            relations = []
            for type_def, targets in term.relationships.items():
                for target in targets:
                    relations.append(f'{type_def.curie} {target.curie}')
                    links.append((term.curie, type_def.curie, target.curie))

            nodes[term.curie] = {
                'id': term.curie,
                'name': term.name,
                'def': term._definition_fp(),
                'xref': [
                    xref.curie
                    for xref in term.xrefs
                ],
                'is_a': parents,
                'relationship': relations,
                'synonym': [
                    synonym._fp()
                    for synonym in term.synonyms
                ],
            }

        for source, key, target in links:
            rv.add_edge(source, target, key=key)

        return rv


def _convert_synonym_type_defs(synonym_type_defs: Iterable[SynonymTypeDef]) -> List[str]:
    """Convert the synonym type defs."""
    return [
        _convert_synonym_type_def(synonym_type_def)
        for synonym_type_def in synonym_type_defs
    ]


def _convert_synonym_type_def(synonym_type_def: SynonymTypeDef) -> str:
    return f'{synonym_type_def.id} "{synonym_type_def.name}"'


def _convert_type_defs(type_defs: Iterable[TypeDef]) -> List[Mapping[str, Any]]:
    """Convert the type defs."""
    return [
        _convert_type_def(type_def)
        for type_def in type_defs
    ]


def _convert_type_def(type_def: TypeDef) -> Mapping[str, Any]:
    """Convert a type def."""
    return dict(
        id=type_def.identifier,
        name=type_def.name,
    )
