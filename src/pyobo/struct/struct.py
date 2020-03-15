# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, TextIO, Union

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
        return Reference(prefix=prefix, identifier=identifier)

    @staticmethod
    def from_curies(curies: str) -> List[Reference]:
        """Get a list of references from a string with comma separated CURIEs."""
        return [
            Reference.from_curie(curie)
            for curie in curies.split(',')
            if curie.strip()
        ]

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
        x = f'synonym: "{self.name}" {self.specificity}'
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


@dataclass
class TypeDef:
    """A type definition in OBO."""

    id: str
    name: str
    comment: Optional[str] = None
    namespace: Optional[str] = None
    is_transitive: Optional[bool] = None
    xrefs: List[Reference] = field(default_factory=list)

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield '\n[Typedef]'
        yield f'id: {self.id}'
        yield f'name: {self.name}'

        if self.namespace:
            yield f'namespace: {self.namespace}'

        if self.comment:
            yield f'comment: {self.comment}'

        for xref in self.xrefs:
            yield f'xref: {xref}'

        if self.is_transitive is not None:
            yield f'is_transitive: {"true" if self.is_transitive else "false"}'

    def to_obo(self) -> str:
        """Get the OBO document string."""
        return '\n'.join(self.iterate_obo_lines())


@dataclass
class Term:
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: Optional[str] = None

    #: References to articles in which the term appears
    provenance: List[Reference] = field(default_factory=list)

    #: Relationships defined by [Typedef] stanzas
    relationships: Dict[str, List[Reference]] = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: List[Reference] = field(default_factory=list)

    #: Synonyms of this term
    synonyms: List[Synonym] = field(default_factory=list)

    #: Equivalent references
    xrefs: List[Reference] = field(default_factory=list)

    name: Optional[str] = None

    #: The sub-namespace within the ontology
    namespace: Optional[str] = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: Optional[bool] = None

    def get_relationships(self, type_def: TypeDef) -> List[Reference]:
        """Get relationships from the given type."""
        return self.relationships[type_def.id]

    def append_relationship(self, type_def: TypeDef, reference: Reference) -> None:
        """Append a relationship."""
        self.relationships[type_def.id].append(reference)

    def extend_relationship(self, type_def: TypeDef, references: Iterable[Reference]) -> None:
        """Append several relationships."""
        self.relationships[type_def.id].extend(references)

    @property
    def identifier(self) -> str:  # noqa: D401
        """The local unique identifier for this term."""
        return self.reference.identifier

    @property
    def curie(self) -> str:  # noqa: D401
        """The CURIE for this term."""
        return self.reference.curie

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
            yield f'''def: "{self.definition}" [{comma_separate(self.provenance)}]'''

        for xref in sorted(self.xrefs, key=attrgetter('prefix', 'identifier')):
            yield f'xref: {xref}'

        for parent in sorted(self.parents, key=attrgetter('prefix', 'identifier')):
            yield f'is_a: {parent}'

        for relationship, relationship_references in sorted(self.relationships.items()):
            for relationship_reference in relationship_references:
                yield f'relationship: {relationship} {relationship_reference}'

        for synonym in sorted(self.synonyms, key=attrgetter('name')):
            yield synonym.to_obo()

    def to_obo(self) -> str:
        """Get the OBO document string."""
        return '\n'.join(self.iterate_obo_lines())


@dataclass
class Obo:
    """An OBO document."""

    #: The prefix for the ontology
    ontology: str

    #: The name of the ontology
    name: str

    #: Terms
    terms: List[Term]

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

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f'format-version: {self.format_version}'
        yield f'date: {self.date.strftime("%d:%m:%Y %H:%M")}'

        if self.auto_generated_by is not None:
            yield f'auto-generated-by: {self.auto_generated_by}'

        if self.data_version is not None:
            yield f'data-version: {self.data_version}'

        for synonym_typedef in sorted(self.synonym_typedefs, key=attrgetter('id')):
            yield synonym_typedef.to_obo()

        yield f'ontology: {self.ontology}'

        for typedef in self.typedefs:
            yield from typedef.iterate_obo_lines()

        for term in self.terms:
            yield from term.iterate_obo_lines()

    def to_obo(self) -> str:
        """Get the OBO document string."""
        return '\n'.join(self.iterate_obo_lines())

    @open_file(1, mode='w')
    def write(self, file: Union[None, str, TextIO, Path] = None) -> None:
        """Write the OBO to a file."""
        print(self.to_obo(), file=file)

    def write_default(self) -> None:
        """Write the OBO to the default path."""
        path = get_prefix_obo_path(self.ontology)
        self.write(path)

    def __iter__(self):  # noqa: D105
        return iter(self.terms)
