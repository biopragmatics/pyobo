# -*- coding: utf-8 -*-

"""Ontology term data structure."""

from collections import defaultdict
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Any, Collection, Dict, Iterable, List, Optional, Tuple, Union

from .extra import Synonym, SynonymTypeDef
from .reference import Reference, Referenced
from .typedef import TypeDef, from_species
from .utils import comma_separate
from ..constants import NCBITAXON_PREFIX
from ..identifier_utils import normalize_curie

__all__ = [
    "Term",
]

ReferenceHint = Union[Reference, "Term", Tuple[str, str], str]


def _ensure_ref(reference: ReferenceHint) -> Reference:
    if reference is None:
        raise ValueError("can not append null reference")
    if isinstance(reference, Term):
        return reference.reference
    if isinstance(reference, str):
        return Reference.from_curie(reference)
    if isinstance(reference, tuple):
        return Reference(*reference)
    if isinstance(reference, Reference):
        return reference
    raise TypeError


def _sort_relations(r):
    typedef, _references = r
    return typedef.reference.name or typedef.reference.identifier


@dataclass
class Term(Referenced):
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: Optional[str] = None

    #: References to articles in which the term appears
    provenance: List[Reference] = field(default_factory=list)

    #: Relationships defined by [Typedef] stanzas
    relationships: Dict[TypeDef, List[Reference]] = field(default_factory=lambda: defaultdict(list))

    #: Properties, which are not defined with Typedef and have scalar values instead of references.
    properties: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: List[Reference] = field(default_factory=list)

    #: Synonyms of this term
    synonyms: List[Synonym] = field(default_factory=list)

    #: Equivalent references
    xrefs: List[Reference] = field(default_factory=list)

    #: Alternate Identifiers
    alt_ids: List[Reference] = field(default_factory=list)

    #: The sub-namespace within the ontology
    namespace: Optional[str] = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: Optional[bool] = None

    def __hash__(self):  # noqa: D105
        return hash((self.__class__, self.prefix, self.identifier))

    @classmethod
    def from_triple(
        cls,
        prefix: str,
        identifier: str,
        name: Optional[str] = None,
        definition: Optional[str] = None,
    ) -> "Term":
        """Create a term from a reference."""
        return cls(
            reference=Reference(prefix=prefix, identifier=identifier, name=name),
            definition=definition,
        )

    @classmethod
    def auto(
        cls,
        prefix: str,
        identifier: str,
    ) -> "Term":
        """Create a term from a reference."""
        from ..api import get_definition

        return cls(
            reference=Reference.auto(prefix=prefix, identifier=identifier),
            definition=get_definition(prefix, identifier),
        )

    @classmethod
    def from_curie(cls, curie: str, name: Optional[str] = None) -> "Term":
        """Create a term directly from a CURIE and optional name."""
        prefix, identifier = normalize_curie(curie)
        return cls.from_triple(prefix=prefix, identifier=identifier, name=name)

    def get_url(self) -> Optional[str]:
        """Return a URL for this term's reference, if possible."""
        return self.reference.get_url()

    def append_provenance(self, reference: ReferenceHint) -> None:
        """Add a provenance reference."""
        self.provenance.append(_ensure_ref(reference))

    def append_synonym(
        self, synonym: Union[str, Synonym], type: Optional[SynonymTypeDef] = None
    ) -> None:
        """Add a synonym."""
        if isinstance(synonym, str):
            synonym = Synonym(synonym, type=type)
        self.synonyms.append(synonym)

    def append_alt(self, alt: Union[str, Reference]) -> None:
        """Add an alternative identifier."""
        if isinstance(alt, str):
            alt = Reference(prefix=self.prefix, identifier=alt)
        self.alt_ids.append(alt)

    def append_parent(self, reference: ReferenceHint) -> None:
        """Add a parent to this entity."""
        self.parents.append(_ensure_ref(reference))

    def extend_parents(self, references: Collection[Reference]) -> None:
        """Add a collection of parents to this entity."""
        if any(x is None for x in references):
            raise ValueError("can not append a collection of parents containing a null parent")
        self.parents.extend(references)

    def get_properties(self, prop) -> List[str]:
        """Get properties from the given key."""
        return self.properties[prop]

    def get_property(self, prop) -> Optional[str]:
        """Get a single property of the given key."""
        r = self.get_properties(prop)
        if not r:
            return
        if len(r) != 1:
            raise
        return r[0]

    def get_relationship(self, typedef: TypeDef) -> Optional[Reference]:
        """Get a single relationship of the given type."""
        r = self.get_relationships(typedef)
        if not r:
            return
        if len(r) != 1:
            raise
        return r[0]

    def get_relationships(self, typedef: TypeDef) -> List[Reference]:
        """Get relationships from the given type."""
        return self.relationships[typedef]

    def append_xref(self, reference: ReferenceHint) -> None:
        """Append an xref."""
        self.xrefs.append(_ensure_ref(reference))

    def append_relationship(self, typedef: TypeDef, reference: ReferenceHint) -> None:
        """Append a relationship."""
        self.relationships[typedef].append(_ensure_ref(reference))

    def set_species(self, identifier: str, name: Optional[str] = None):
        """Append the from_species relation."""
        if name is None:
            import pyobo

            name = pyobo.get_name(NCBITAXON_PREFIX, identifier)
        self.append_relationship(
            from_species, Reference(prefix=NCBITAXON_PREFIX, identifier=identifier, name=name)
        )

    def get_species(self, prefix: str = NCBITAXON_PREFIX) -> Optional[Reference]:
        """Get the species if it exists.

        :param prefix: The prefix to use in case the term has several species annotations.
        """
        for species in self.relationships.get(from_species, []):
            if species.prefix == prefix:
                return species

    def extend_relationship(self, typedef: TypeDef, references: Iterable[Reference]) -> None:
        """Append several relationships."""
        if any(x is None for x in references):
            raise ValueError("can not extend a collection that includes a null reference")
        self.relationships[typedef].extend(references)

    def append_property(self, prop: str, value: str) -> None:
        """Append a property."""
        self.properties[prop].append(value)

    def _definition_fp(self) -> str:
        return f'"{self._escape(self.definition)}" [{comma_separate(self.provenance)}]'

    def iterate_relations(self) -> Iterable[Tuple[TypeDef, Reference]]:
        """Iterate over pairs of typedefs and targets."""
        for typedef, targets in self.relationships.items():
            for target in targets:
                yield typedef, target

    def iterate_properties(self) -> Iterable[Tuple[str, str]]:
        """Iterate over pairs of property and values."""
        for prop, values in self.properties.items():
            for value in values:
                yield prop, value

    def iterate_obo_lines(self, write_relation_comments: bool = True) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield "\n[Term]"
        yield f"id: {self.curie}"
        if self.name:
            yield f"name: {self.name}"
        if self.namespace and self.namespace != "?":
            namespace_normalized = (
                self.namespace.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
            )
            yield f"namespace: {namespace_normalized}"

        if self.definition:
            yield f"def: {self._definition_fp()}"

        for xref in sorted(self.xrefs, key=attrgetter("prefix", "identifier")):
            yield f"xref: {xref}"

        for parent in sorted(self.parents, key=attrgetter("prefix", "identifier")):
            yield f"is_a: {parent}"

        for typedef, references in sorted(self.relationships.items(), key=_sort_relations):
            for reference in references:
                s = f"relationship: {typedef.curie} {reference.curie}"
                if write_relation_comments:
                    # TODO Obonet doesn't support this. re-enable later.
                    if typedef.name or reference.name:
                        s += " !"
                    if typedef.name:
                        s += f" {typedef.name}"
                    if reference.name:
                        s += f" {reference.name}"
                yield s

        for prop, value in self.iterate_properties():
            yield f'property_value: {prop} "{value}" xsd:string'  # TODO deal with types later

        for synonym in sorted(self.synonyms, key=attrgetter("name")):
            yield synonym.to_obo()

    @staticmethod
    def _escape(s) -> str:
        return s.replace('"', '\\"')
