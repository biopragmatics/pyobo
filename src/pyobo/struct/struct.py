# -*- coding: utf-8 -*-

"""Data structures for OBO."""

from __future__ import annotations

import gzip
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, TextIO, Tuple, Union

import networkx as nx
import pandas as pd
from networkx.utils import open_file

from .reference import Reference, Referenced
from .typedef import TypeDef, is_a
from .utils import comma_separate
from ..identifier_utils import PREFIX_REMAP, XREF_BLACKLIST, XREF_PREFIX_BLACKLIST, normalize_curie, normalize_prefix
from ..io_utils import multidict
from ..path_utils import get_prefix_obo_path

__all__ = [
    'Synonym',
    'SynonymTypeDef',
    'Term',
    'Obo',
]

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d:%m:%Y %H:%M"
COLUMNS = ['source_ns', 'source_id', 'target_ns', 'target_id']


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

    def append_property(self, prop: str, value: str) -> None:
        """Append a property."""
        self.properties[prop].append(value)

    def _definition_fp(self):
        return f'"{self.definition}" [{comma_separate(self.provenance)}]'

    def iterate_properties(self) -> Iterable[str, str]:
        """Iterate over pairs of property and values."""
        for prop, values in self.properties.items():
            for value in values:
                yield prop, value

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

        # TODO add properties

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
    iter_terms: Callable[[], Iterable[Term]] = field(repr=False)

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

    #: The hierarchy of terms
    _hierarchy: Optional[nx.DiGraph] = field(init=False, default=None)

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return self.date.strftime(DATE_FORMAT)

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

    def is_descendant(self, identifier: str, ancestor: str) -> bool:
        """Return if the given identifier is a descendent of the ancestor.

        .. code-block:: python

            from pyobo import get_obo
            obo = get_obo('go')

            interleukin_10_complex = '1905571'  # interleukin-10 receptor complex
            all_complexes = '0032991'
            assert obo.is_descendant('1905571', '0032991')
        """
        return ancestor in nx.descendants(self.hierarchy, identifier)

    @property
    def hierarchy(self) -> nx.DiGraph:  # noqa: D401
        """A graph representing the parent/child relationships between the entities.

        To get all children of a given entity, do:

        .. code-block:: python

            from pyobo import get_obo
            obo = get_obo('go')

            identifier = '1905571'  # interleukin-10 receptor complex
            is_complex = '0032991' in  nx.descendants(obo.hierarchy, identifier)  # should be true
        """
        if self._hierarchy is None:
            self._hierarchy = nx.DiGraph()
            for term in self:
                for parent in term.parents:
                    self._hierarchy.add_edge(term.identifier, parent.identifier)
        return self._hierarchy

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
        for term in self:
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

    @staticmethod
    def from_obonet(graph: nx.MultiDiGraph):
        """Get all of the terms from a OBO graph."""
        ontology = graph.graph['ontology'].lower()  # probably always okay
        logger.info('parsing OBO from %s', ontology)

        #: Parsed CURIEs to references (even external ones)
        references: Mapping[Tuple[str, str], Reference] = {
            (prefix, identifier): Reference(
                prefix=prefix,
                identifier=identifier,
                name=data.get('name'),  # if name isn't available, it means its external to this ontology
            )
            for prefix, identifier, data in _iter_obo_graph(graph=graph)
        }
        logger.info('extracted %d references from %s', len(references), ontology)

        #: CURIEs to typedefs
        typedefs: Mapping[Tuple[str, str], TypeDef] = {
            (typedef.prefix, typedef.identifier): typedef
            for typedef in iterate_graph_typedefs(graph, ontology)
        }
        logger.info('extracted %d typedefs from %s', len(typedefs), ontology)

        synonym_typedefs: Mapping[str, SynonymTypeDef] = {
            synonym_typedef.id: synonym_typedef
            for synonym_typedef in iterate_graph_synonym_typedefs(graph)
        }
        logger.info('extracted %d synonym typedefs from %s', len(synonym_typedefs), ontology)

        def _iter_terms() -> Iterable[Term]:
            for prefix, identifier, data in _iter_obo_graph(graph=graph):
                if prefix != ontology or not data:
                    continue

                xrefs, provenance = [], []
                for reference in iterate_node_xrefs(data):
                    if reference.prefix == 'pubmed':
                        provenance.append(reference)
                    else:
                        xrefs.append(reference)

                reference = references[ontology, identifier]

                definition = data.get('def')  # it's allowed not to have a definition

                term = Term(
                    reference=reference,
                    definition=definition,
                    parents=list(iterate_node_parents(data)),
                    synonyms=list(iterate_node_synonyms(data)),
                    xrefs=xrefs,
                    provenance=provenance,
                )
                for relation, reference in iterate_node_relationships(data, ontology):
                    term.append_relationship(typedefs[relation.prefix, relation.identifier], reference)
                for prop, value in iterate_node_properties(data):
                    term.append_property(prop, value)
                yield term

        try:
            date = datetime.strptime(graph.graph['date'], DATE_FORMAT)
        except KeyError:
            date = None

        return Obo(
            ontology=ontology,
            name=graph.graph['name'],
            auto_generated_by=graph.graph.get('auto-generated-by'),
            format_version=graph.graph.get('format-version'),
            date=date,
            typedefs=list(typedefs.values()),
            synonym_typedefs=list(synonym_typedefs.values()),
            iter_terms=_iter_terms,
        )

    def get_id_name_mapping(self) -> Mapping[str, str]:
        """Get a mapping from identifiers to names."""
        return {
            term.identifier: term.name
            for term in self
        }

    def iterate_synonyms(self) -> Iterable[Tuple[Term, Synonym]]:
        """Iterate over synonyms for each term."""
        for term in self:
            for synonym in term.synonyms:
                yield term, synonym

    def iterate_properties(self) -> Iterable[Tuple[Term, str, str]]:
        """Iterate over tuples of terms, properties, and their values."""
        for term in self:
            for prop, value in term.iterate_properties():
                yield term, prop, value

    def iterate_relations(self) -> Iterable[Tuple[Term, TypeDef, Reference]]:
        """Iterate over tuples of terms, relations, and their targets."""
        for term in self:
            for parent in term.parents:
                yield term, is_a, parent
            for typedef, references in term.relationships.items():
                for reference in references:
                    yield term, typedef, reference

    def get_relations_df(self) -> pd.DataFrame:
        """Get all relations from the OBO."""
        return pd.DataFrame(
            [
                (term.identifier, typedef.prefix, typedef.identifier, reference.prefix, reference.identifier)
                for term, typedef, reference in self.iterate_relations()
            ],
            columns=[f'{self.ontology}_id', 'relation_ns', 'relation_id', 'target_ns', 'target_id'],
        )

    def iterate_filtered_xrefs(self, prefix: str) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over xrefs to a given prefix."""
        for term in self:
            for xref in term.xrefs:
                if xref.prefix == prefix:
                    yield term, xref

    def get_xrefs_df(self) -> pd.DataFrame:
        """Get a dataframe of all xrefs extracted from the OBO document."""
        return pd.DataFrame(
            [
                (term.prefix, term.identifier, xref.prefix, xref.identifier)
                for term in self
                for xref in term.xrefs
            ],
            columns=COLUMNS,
        )

    def get_filtered_xrefs_mapping(self, prefix: str) -> Mapping[str, str]:
        """Get filtered xrefs as a dictionary."""
        return {
            term.identifier: xref.identifier
            for term, xref in self.iterate_filtered_xrefs(prefix)
        }

    def get_filtered_multixrefs_mapping(self, prefix: str) -> Mapping[str, List[str]]:
        """Get filtered xrefs as a dictionary."""
        return multidict(
            (term.identifier, xref.identifier)
            for term, xref in self.iterate_filtered_xrefs(prefix)
        )

    def get_id_relations_mapping(self, type_def: TypeDef) -> Mapping[str, List[Reference]]:
        """Get a mapping from identifiers to a list of all references for the given relation."""
        return multidict(
            (term.identifier, reference)
            for term in self
            for reference in term.relationships.get(type_def)
        )

    def get_id_synonyms_mapping(self) -> Mapping[str, List[str]]:
        """Get a mapping from identifiers to a list of sorted synonym strings."""
        rv = multidict(
            (term.identifier, synonym.name)
            for term, synonym in self.iterate_synonyms()
        )
        return {
            k: sorted(set(v))
            for k, v in rv.items()
        }


def _iter_obo_graph(graph: nx.MultiDiGraph) -> Iterable[Tuple[Optional[str], str, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in graph.nodes(data=True):
        prefix, identifier = normalize_curie(node)
        if prefix and identifier:
            yield prefix, identifier, data


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


def iterate_graph_synonym_typedefs(graph: nx.MultiDiGraph) -> Iterable[SynonymTypeDef]:
    """Get synonym type definitions from an :mod:`obonet` graph."""
    for s in graph.graph.get('synonymtypedef', []):
        sid, name = s.split(' ', 1)
        name = name.strip().strip('"')
        yield SynonymTypeDef(id=sid, name=name)


def iterate_graph_typedefs(graph: nx.MultiDiGraph, default_prefix: str) -> Iterable[TypeDef]:
    """Get type definitions from an :mod:`obonet` graph."""
    for typedef in graph.graph.get('typedefs', []):
        name = typedef['name']

        prefix, identifier = normalize_curie(typedef['id'])
        if prefix is None and identifier is None:
            prefix, identifier = default_prefix, typedef['id']

        reference = Reference(prefix=prefix, identifier=identifier, name=name)

        xrefs = [
            Reference.from_curie(curie)
            for curie in typedef.get('xref', [])
        ]
        yield TypeDef(reference=reference, xrefs=xrefs)


def iterate_node_synonyms(data: Mapping[str, Any]) -> Iterable[Synonym]:
    """Extract synonyms from a :mod:`obonet` node's data."""
    for s in data.get('synonym', []):
        s = s.strip('"')
        if not s:
            continue

        # TODO check if the synonym is written like a CURIE... it shouldn't but I've seen it happen

        if "RELATED" in s:
            name = s[:s.index('RELATED')].rstrip().rstrip('"')
            specificity = 'RELATED'
        elif "EXACT" in s:
            name = s[:s.index('EXACT')].rstrip().rstrip('"')
            specificity = 'EXACT'
        elif "BROAD" in s:
            name = s[:s.index('BROAD')].rstrip().rstrip('"')
            specificity = 'BROAD'
        elif "NARROW" in s:
            name = s[:s.index('NARROW')].rstrip().rstrip('"')
            specificity = 'NARROW'
        else:
            logger.warning(f'For unhandled synonym: {s}')
            continue

        yield Synonym(name=name, specificity=specificity)


HANDLED_PROPERTY_TYPES = {
    'xsd:string': str,
    'xsd:dateTime': datetime,
}


def iterate_node_properties(
    data: Mapping[str, Any],
    property_prefix: Optional[str] = None,
) -> Iterable[Tuple[str, str]]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get('property_value', []):
        prop, value_type = prop_value_type.split(' ', 1)
        if property_prefix is not None and prop.startswith(property_prefix):
            prop = prop[len(property_prefix):]

        try:
            value, _ = value_type.rsplit(' ', 1)  # second entry is the value type
        except ValueError:
            logger.debug(f'property missing datatype. defaulting to string - {prop_value_type}')
            value = value_type  # could assign type to be 'xsd:string' by default
        value = value.strip('"')
        yield prop, value


def iterate_node_parents(data: Mapping[str, Any]) -> Iterable[Reference]:
    """Extract parents from a :mod:`obonet` node's data."""
    for parent_curie in data.get('is_a', []):
        yield Reference.from_curie(parent_curie)


def iterate_node_relationships(data: Mapping[str, Any], default_prefix: str) -> Iterable[Tuple[Reference, Reference]]:
    """Extract relationships from a :mod:`obonet` node's data."""
    for s in data.get('relationship', []):
        relation_curie, target_curie = s.split(' ')
        relation_prefix, relation_identifier = normalize_curie(relation_curie)
        if relation_prefix is None and relation_identifier is None:
            relation_prefix, relation_identifier = default_prefix, relation_curie
        relation = Reference(prefix=relation_prefix, identifier=relation_identifier)
        target = Reference.from_curie(target_curie)
        yield relation, target


def iterate_node_xrefs(data: Mapping[str, Any]) -> Iterable[Reference]:
    """Extract xrefs from a :mod:`obonet` node's data."""
    for xref in data.get('xref', []):
        xref = xref.strip()

        if (
            any(xref.startswith(x) for x in XREF_PREFIX_BLACKLIST)
            or xref in XREF_BLACKLIST
            or ':' not in xref
        ):
            continue  # sometimes xref to self... weird

        for blacklisted_prefix, new_prefix in PREFIX_REMAP.items():
            if xref.startswith(blacklisted_prefix):
                xref = new_prefix + xref[len(blacklisted_prefix):]

        split_space = ' ' in xref
        if split_space:
            _xref_split = xref.split(' ', 1)
            if _xref_split[1][0] not in {'"', '('}:
                logger.warning(f'Problem with space in xref {xref}')
                continue
            xref = _xref_split[0]

        try:
            xref_prefix, xref_identifier = xref.split(':', 1)
        except ValueError:
            if split_space:
                logger.warning(f'problem splitting after space split {xref}')
            else:
                logger.warning(f'problem splitting {xref}')

            continue

        norm_xref_prefix = normalize_prefix(xref_prefix)
        if not norm_xref_prefix:
            continue

        yield Reference(prefix=norm_xref_prefix, identifier=xref_identifier)
