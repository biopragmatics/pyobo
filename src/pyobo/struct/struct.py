# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, TextIO, Union

from .utils import comma_separate, obo_escape

__all__ = [
    'Reference',
    'Synonym',
    'TypeDef',
    'Term',
    'Obo',
]


@dataclass
class Reference:
    """A namespace, identifier, and label."""

    #: The entity's identifier in the namespace
    identifier: str

    #: The namespace's keyword
    namespace: str

    #: The entity's name/label
    name: Optional[str] = None

    @property
    def curie(self) -> str:
        """The CURIE for this reference."""
        return f'{self.namespace}:{self.identifier}'

    @staticmethod
    def from_curie(curie: str) -> 'Reference':
        """Get a reference from a CURIE."""
        namespace, identifier = curie.strip().split(':')
        return Reference(namespace=namespace, identifier=identifier)

    @staticmethod
    def from_curies(curies: str) -> List['Reference']:
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
        if self.identifier.startswith(f'{self.namespace}:'):
            curie = self.identifier
        else:
            curie = f'{self.namespace}:{self._escaped_identifier}'

        if not self.name:
            return curie

        return f'{curie} ! {self.name}'


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: str

    #: References to articles where the synonym appears
    provenance: List[Reference] = field(default_factory=list)

    def to_obo(self) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f'synonym: "{self.name}" {self.specificity} [{comma_separate(self.provenance)}]'


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
    definition: str

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

    #: The sub-namespace within the ontology
    namespace: Optional[str] = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: Optional[bool] = None

    @property
    def curie(self) -> str:
        """The CURIE for this term."""
        return self.reference.curie

    def iterate_obo_lines(self) -> Iterable[str]:
        yield '\n[Term]'
        yield f'id: {self.reference.namespace}:{self.reference.identifier}'
        yield f'name: {self.reference.name}'
        if self.namespace and self.namespace != '?':
            namespace_normalized = self.namespace \
                .replace(' ', '_') \
                .replace('-', '_') \
                .replace('(', '') \
                .replace(')', '')
            yield f'namespace: {namespace_normalized}'
        yield f'''def: "{self.definition}" [{comma_separate(self.provenance)}]'''

        for xref in self.xrefs:
            yield f'xref: {xref}'

        for parent in self.parents:
            yield f'is_a: {parent}'

        for relationship, relationship_references in self.relationships.items():
            for relationship_reference in relationship_references:
                yield f'relationship: {relationship} {relationship_reference}'

        for synonym in self.synonyms:
            yield synonym.to_obo()

    def to_obo(self) -> str:
        """Get the OBO document string."""
        return '\n'.join(self.iterate_obo_lines())


@dataclass
class Obo:
    """An OBO document."""

    #: The name of the ontology
    ontology: str

    #: Type definitions
    typedefs: List[TypeDef]

    #: Terms
    terms: List[Term]

    #: The OBO format
    format_version: str = '1.2'

    #: The ontology version
    data_version: Optional[str] = None

    #: An annotation about how an ontology was generated
    auto_generated_by: Optional[str] = None

    #: The date the ontology was generated
    date: datetime = field(default_factory=datetime.today)

    # _references: Mapping[str, Reference] = field(init=False)
    #
    # def __post_init__(self) -> None:
    #     """Index all of the references."""
    #     for term in self.terms:
    #         self._references[term]

    def iterate_obo_lines(self) -> Iterable[str]:
        yield f'format-version: {self.format_version}'
        yield f'date: {self.date.strftime("%d:%m:%Y %H:%M")}'

        if self.auto_generated_by is not None:
            yield f'auto-generated-by: {self.auto_generated_by}'

        yield f'ontology: {self.ontology}'

        for typedef in self.typedefs:
            yield from typedef.iterate_obo_lines()

        for term in self.terms:
            yield from term.iterate_obo_lines()

    def to_obo(self) -> str:
        """Get the OBO document string."""
        return '\n'.join(self.iterate_obo_lines())

    def write(self, file: Union[None, TextIO, Path] = None) -> None:
        """Write the OBO to a file."""
        print(self.to_obo(), file=file)
