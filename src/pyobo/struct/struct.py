# -*- coding: utf-8 -*-

"""Data structures for OBO."""

import gzip
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Union,
)

import networkx as nx
import pandas as pd
from more_itertools import pairwise
from networkx.utils import open_file
from tqdm import tqdm

from .reference import Reference, Referenced
from .typedef import (
    RelationHint,
    TypeDef,
    default_typedefs,
    develops_from,
    from_species,
    get_reference_tuple,
    has_part,
    is_a,
    orthologous,
    part_of,
)
from .utils import comma_separate
from ..constants import RELATION_ID, RELATION_PREFIX, TARGET_ID, TARGET_PREFIX
from ..identifier_utils import MissingPrefix, normalize_curie, normalize_prefix
from ..registries import get_remappings_prefix, get_xrefs_blacklist, get_xrefs_prefix_blacklist
from ..utils.cache import get_gzipped_graph
from ..utils.io import multidict, write_iterable_tsv
from ..utils.path import get_prefix_obo_path, prefix_directory_join

__all__ = [
    "Synonym",
    "SynonymTypeDef",
    "Term",
    "Obo",
]

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d:%m:%Y %H:%M"
PROVENANCE_PREFIXES = {
    "pubmed",
    "pmc",
    "doi",
    "biorxiv",
    "chemrxiv",
    "wikipedia",
    "google.patent",
    "agricola",
    "cba",
    "ppr",
    "citexplore",
    "goc",
    "isbn",
    "issn",
}


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: str = "EXACT"

    #: The type of synonym. Must be defined in OBO document!
    type: Optional["SynonymTypeDef"] = None

    #: References to articles where the synonym appears
    provenance: List[Reference] = field(default_factory=list)

    def to_obo(self) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f"synonym: {self._fp()}"

    def _fp(self) -> str:
        x = f'"{self.name}" {self.specificity}'
        if self.type:
            x = f"{x} {self.type.id}"
        return f"{x} [{comma_separate(self.provenance)}]"


@dataclass
class SynonymTypeDef:
    """A type definition for synonyms in OBO."""

    id: str
    name: str

    def to_obo(self) -> str:
        """Serialize to OBO."""
        return f'synonymtypedef: {self.id} "{self.name}"'

    @classmethod
    def from_text(cls, text) -> "SynonymTypeDef":
        """Get a type definition from text that's normalized."""
        return cls(
            id=text.lower()
            .replace("-", "_")
            .replace(" ", "_")
            .replace('"', "")
            .replace(")", "")
            .replace("(", ""),
            name=text.replace('"', ""),
        )


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

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: Optional[str] = None) -> "Term":
        """Create a term from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def from_curie(cls, curie: str, name: Optional[str] = None) -> "Term":
        """Create a term directly from a CURIE and optional name."""
        prefix, identifier = normalize_curie(curie)
        return cls.from_triple(prefix=prefix, identifier=identifier, name=name)

    def append_parent(self, reference: Union["Term", Reference]) -> None:
        """Add a parent to this entity."""
        if reference is None:
            raise ValueError("can not append a null parent")
        if isinstance(reference, Term):
            reference = reference.reference
        self.parents.append(reference)

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

    def append_xref(self, reference: Union[Reference, "Term"]) -> None:
        """Append an xref."""
        if isinstance(reference, Term):
            reference = reference.reference
        self.xrefs.append(reference)

    def append_relationship(self, typedef: TypeDef, reference: Union[Reference, "Term"]) -> None:
        """Append a relationship."""
        if reference is None:
            raise ValueError("can not append null reference")
        if isinstance(reference, Term):
            reference = reference.reference
        self.relationships[typedef].append(reference)

    def set_species(self, identifier: str, name: Optional[str] = None):
        """Append the from_species relation."""
        if name is None:
            import pyobo

            name = pyobo.get_name("ncbitaxon", identifier)
        self.append_relationship(
            from_species, Reference(prefix="ncbitaxon", identifier=identifier, name=name)
        )

    def get_species(self, prefix: str = "ncbitaxon") -> Optional[Reference]:
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
        return f'"{self.definition}" [{comma_separate(self.provenance)}]'

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

    def iterate_obo_lines(self, write_relation_comments: bool = False) -> Iterable[str]:
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


def _sort_relations(r):
    typedef, _references = r
    return typedef.reference.name or typedef.reference.identifier


@dataclass
class Obo:
    """An OBO document."""

    #: The prefix for the ontology
    ontology: str

    #: The name of the ontology
    name: str

    #: A function that iterates over terms
    iter_terms: Callable[..., Iterable[Term]] = field(repr=False)

    #: The OBO format
    format_version: str = "1.2"

    #: Type definitions
    typedefs: List[TypeDef] = field(default_factory=list)

    #: Synonym type definitions
    synonym_typedefs: List[SynonymTypeDef] = field(default_factory=list)

    #: Kwargs to add to the iter_items when called
    iter_terms_kwargs: Optional[Mapping[str, Any]] = None

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

    #: For super-sized datasets that shouldn't be read into memory
    iter_only: bool = False

    _items: Optional[List[Term]] = field(init=False, default=None)

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return (self.date if self.date else datetime.now()).strftime(DATE_FORMAT)

    def _iter_terms(self, use_tqdm: bool = False, desc: str = "terms") -> Iterable[Term]:
        if use_tqdm:
            try:
                total = len(self._items)
            except TypeError:
                total = None
            yield from tqdm(self, desc=desc, unit_scale=True, unit="term", total=total)
        else:
            yield from self

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f"format-version: {self.format_version}"
        yield f"date: {self.date_formatted}"

        if self.auto_generated_by is not None:
            yield f"auto-generated-by: {self.auto_generated_by}"

        if self.data_version is not None:
            yield f"data-version: {self.data_version}"

        for synonym_typedef in sorted(self.synonym_typedefs, key=attrgetter("id")):
            yield synonym_typedef.to_obo()

        yield f"ontology: {self.ontology}"

        for typedef in self.typedefs:
            yield from typedef.iterate_obo_lines()

        for term in self:
            yield from term.iterate_obo_lines()

    @open_file(1, mode="w")
    def write_obo(
        self, file: Union[None, str, TextIO, Path] = None, use_tqdm: bool = False
    ) -> None:
        """Write the OBO to a file."""
        it = self.iterate_obo_lines()
        if use_tqdm:
            it = tqdm(it, desc=f"writing {self.ontology}", unit_scale=True, unit="line")
        for line in it:
            print(line, file=file)  # noqa:T001

    def write_obonet_gz(self, path: Union[str, Path]) -> None:
        """Write the OBO to a gzipped dump in Obonet JSON."""
        graph = self.to_obonet()
        with gzip.open(path, "wt") as file:
            json.dump(nx.node_link_data(graph), file)

    @classmethod
    def from_obonet_gz(cls, path: Union[str, Path]) -> "Obo":
        """Read OBO from a pre-compiled Obonet JSON."""
        return cls.from_obonet(get_gzipped_graph(path))

    def _path(self, *parts: str, name: Optional[str] = None) -> Path:
        return prefix_directory_join(self.ontology, *parts, name=name, version=self.data_version)

    def _cache(self, *parts: str, name: Optional[str] = None) -> Path:
        return self._path("cache", *parts, name=name)

    @property
    def _names_path(self) -> Path:
        return self._cache(name="names.tsv")

    @property
    def _definitions_path(self) -> Path:
        return self._cache(name="definitions.tsv")

    @property
    def _species_path(self) -> Path:
        return self._cache(name="species.tsv")

    @property
    def _synonyms_path(self) -> Path:
        return self._cache(name="synonyms.tsv")

    @property
    def _alts_path(self):
        return self._cache(name="alt_ids.tsv")

    @property
    def _typedefs_path(self) -> Path:
        return self._cache(name="typedefs.tsv")

    @property
    def _xrefs_path(self) -> Path:
        return self._cache(name="xrefs.tsv")

    @property
    def _relations_path(self) -> Path:
        return self._cache(name="relations.tsv")

    @property
    def _properties_path(self) -> Path:
        return self._cache(name="properties.tsv")

    @property
    def _root_metadata_path(self) -> Path:
        return prefix_directory_join(self.ontology, name="metadata.json")

    @property
    def _versioned_metadata_path(self) -> Path:
        return self._cache(name="metadata.json")

    @property
    def _obo_path(self) -> Path:
        return get_prefix_obo_path(self.ontology, version=self.data_version)

    @property
    def _obonet_gz_path(self) -> Path:
        return self._path(name=f"{self.ontology}.obonet.json.gz")

    def write_default(
        self,
        use_tqdm: bool = False,
        force: bool = False,
        write_obo: bool = False,
        write_obonet: bool = False,
    ) -> None:
        """Write the OBO to the default path."""
        metadata = self.get_metadata()
        for path in (self._root_metadata_path, self._versioned_metadata_path):
            logger.info("[%s] caching metadata to %s", self.ontology, path)
            with path.open("w") as file:
                json.dump(metadata, file, indent=2)

        logger.info("[%s] caching typedefs to %s", self.ontology, self._typedefs_path)
        typedef_df: pd.DataFrame = self.get_typedef_df()
        typedef_df.sort_values(list(typedef_df.columns), inplace=True)
        typedef_df.to_csv(self._typedefs_path, sep="\t", index=False)

        for label, path, header, fn in [
            ("names", self._names_path, [f"{self.ontology}_id", "name"], self.iterate_id_name),
            (
                "definitions",
                self._definitions_path,
                [f"{self.ontology}_id", "definition"],
                self.iterate_id_definition,
            ),
            (
                "species",
                self._species_path,
                [f"{self.ontology}_id", "taxonomy_id"],
                self.iterate_id_species,
            ),
            (
                "synonyms",
                self._synonyms_path,
                [f"{self.ontology}_id", "synonym"],
                self.iterate_synonym_rows,
            ),
            ("alts", self._alts_path, [f"{self.ontology}_id", "alt_id"], self.iterate_alt_rows),
            ("xrefs", self._xrefs_path, self.xrefs_header, self.iterate_xref_rows),
            ("relations", self._relations_path, self.relations_header, self.iter_relation_rows),
            ("properties", self._properties_path, self.properties_header, self.iter_property_rows),
        ]:
            if path.exists() and not force:
                continue
            logger.info("[%s] caching %s to %s", self.ontology, label, path)
            write_iterable_tsv(
                path=path,
                header=header,
                it=fn(),
            )

        for relation in (is_a, has_part, part_of, from_species, orthologous):
            if relation is not is_a and relation not in self.typedefs:
                continue
            relations_path = self._cache("relations", name=f"{relation.curie}.tsv")
            if relations_path.exists() and not force:
                continue
            logger.info(
                "[%s] caching relation %s ! %s", self.ontology, relation.curie, relation.name
            )
            relation_df = self.get_filtered_relations_df(relation)
            if not len(relation_df.index):
                continue
            relation_df.sort_values(list(relation_df.columns), inplace=True)
            relation_df.to_csv(relations_path, sep="\t", index=False)

        if write_obo and (not self._obo_path.exists() or force):
            self.write_obo(self._obo_path, use_tqdm=use_tqdm)

        if write_obonet and (not self._obonet_gz_path.exists() or force):
            logger.info("writing obonet to %s", self._obonet_gz_path)
            self.write_obonet_gz(self._obonet_gz_path)

    def __iter__(self):  # noqa: D105
        if self.iter_only:
            return iter(self.iter_terms(**(self.iter_terms_kwargs or {})))
        if self._items is None:
            self._items = list(self.iter_terms(**(self.iter_terms_kwargs or {})))
        return iter(self._items)

    def ancestors(self, identifier: str) -> Set[str]:
        """Return a set of identifiers for parents of the given identifier."""
        return nx.descendants(self.hierarchy, identifier)  # note this is backwards

    def descendants(self, identifier: str) -> Set[str]:
        """Return a set of identifiers for the children of the given identifier."""
        return nx.ancestors(self.hierarchy, identifier)  # note this is backwards

    def is_descendant(self, descendant: str, ancestor: str) -> bool:
        """Return if the given identifier is a descendent of the ancestor.

        .. code-block:: python

            from pyobo import get_obo
            obo = get_obo('go')

            interleukin_10_complex = '1905571'  # interleukin-10 receptor complex
            all_complexes = '0032991'
            assert obo.is_descendant('1905571', '0032991')
        """
        return ancestor in self.ancestors(descendant)

    @property
    def hierarchy(self, *, use_tqdm: bool = False) -> nx.DiGraph:
        """A graph representing the parent/child relationships between the entities.

        To get all children of a given entity, do:

        .. code-block:: python

            from pyobo import get_obo
            obo = get_obo('go')

            identifier = '1905571'  # interleukin-10 receptor complex
            is_complex = '0032991' in  nx.descendants(obo.hierarchy, identifier)  # should be true
        """  # noqa:D401
        if self._hierarchy is None:
            self._hierarchy = nx.DiGraph()
            for term in self._iter_terms(
                use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting hierarchy"
            ):
                for parent in term.parents:
                    self._hierarchy.add_edge(term.identifier, parent.identifier)
        return self._hierarchy

    def to_obonet(self: "Obo", *, use_tqdm: bool = False) -> nx.MultiDiGraph:
        """Export as a :mod`obonet` style graph."""
        rv = nx.MultiDiGraph()
        rv.graph.update(
            {
                "name": self.name,
                "ontology": self.ontology,
                "auto-generated-by": self.auto_generated_by,
                "typedefs": _convert_typedefs(self.typedefs),
                "format-version": self.format_version,
                "data-version": self.data_version,
                "synonymtypedef": _convert_synonym_typedefs(self.synonym_typedefs),
                "date": self.date_formatted,
            }
        )

        nodes = {}
        links = []
        for term in self._iter_terms(use_tqdm=use_tqdm):
            parents = []
            for parent in term.parents:
                if parent is None:
                    raise ValueError("parent should not be none!")
                links.append((term.curie, "is_a", parent.curie))
                parents.append(parent.curie)

            relations = []
            for typedef, target in term.iterate_relations():
                if target is None:
                    raise ValueError("target should not be none!")
                relations.append(f"{typedef.curie} {target.curie}")
                links.append((term.curie, typedef.curie, target.curie))

            d = {
                "id": term.curie,
                "name": term.name,
                "def": term.definition and term._definition_fp(),
                "xref": [xref.curie for xref in term.xrefs],
                "is_a": parents,
                "relationship": relations,
                "synonym": [synonym._fp() for synonym in term.synonyms],
                "property_value": [
                    f"{prop} {value}"
                    for prop, values in term.properties.items()
                    for value in values
                ],
            }
            nodes[term.curie] = {k: v for k, v in d.items() if v}

        rv.add_nodes_from(nodes.items())
        for source, key, target in links:
            rv.add_edge(source, target, key=key)

        logger.info("[%s] exported graph with %d nodes", self.ontology, rv.number_of_nodes())
        return rv

    @staticmethod
    def _cleanup_version(data_version: str) -> Optional[str]:
        if data_version.replace(".", "").isnumeric():
            return data_version  # consectuive, major.minor, or semantic versioning
        if data_version.startswith("http://www.ebi.ac.uk/efo/releases/v"):
            return data_version[len("http://www.ebi.ac.uk/efo/releases/v") :].split("/")[0]
        for v in data_version.split("/"):
            v = v.strip()
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                continue
            else:
                return v

    @classmethod
    def from_obo_path(
        cls, path: Union[str, Path], prefix: Optional[str] = None, *, strict: bool = True
    ) -> "Obo":
        """Get the OBO graph from a path."""
        import obonet

        logger.info("[%s] parsing with obonet from %s", prefix or "", path)
        with open(path) as file:
            graph = obonet.read_obo(
                tqdm(file, unit_scale=True, desc=f'[{prefix or ""}] parsing obo', disable=None)
            )

        if prefix:
            # Make sure the graph is named properly
            _clean_graph_ontology(graph, prefix)

        # Convert to an Obo instance and return
        obo = Obo.from_obonet(graph, strict=strict)
        return obo

    @staticmethod
    def _get_name(graph, ontology: str) -> str:
        try:
            rv = graph.graph["name"]
        except KeyError:
            logger.info("[%s] does not report a name", ontology)
            rv = ontology
        return rv

    @staticmethod
    def _get_date(graph, ontology: str) -> Optional[datetime]:
        try:
            rv = datetime.strptime(graph.graph["date"], DATE_FORMAT)
        except KeyError:
            logger.info("[%s] does not report a date", ontology)
            rv = None
        return rv

    @classmethod
    def from_obonet(cls, graph: nx.MultiDiGraph, *, strict: bool = True) -> "Obo":
        """Get all of the terms from a OBO graph."""
        ontology = normalize_prefix(graph.graph["ontology"])  # probably always okay
        logger.info("[%s] extracting OBO using obonet", ontology)

        date = cls._get_date(graph=graph, ontology=ontology)
        name = cls._get_name(graph=graph, ontology=ontology)

        data_version = graph.graph.get("data-version")
        if not data_version:
            if date is not None:
                data_version = date.strftime("%Y-%m-%d")
                logger.info(
                    "[%s] does not report a version. falling back to date: %s",
                    ontology,
                    data_version,
                )
            else:
                logger.warning("[%s] does not report a version nor a date", ontology)
        else:
            data_version = cls._cleanup_version(data_version)
            if data_version is not None:
                logger.info("[%s] using version %s", ontology, data_version)
            elif date is not None:
                logger.info(
                    "[%s] unrecognized version format, falling back to date: %s",
                    ontology,
                    data_version,
                )
                data_version = date.strftime("%Y-%m-%d")
            else:
                logger.warning(
                    "[%s] UNRECOGNIZED VERSION FORMAT AND MISSING DATE: %s", ontology, data_version
                )

        #: Parsed CURIEs to references (even external ones)
        references: Mapping[Tuple[str, str], Reference] = {
            (prefix, identifier): Reference(
                prefix=prefix,
                identifier=identifier,
                # if name isn't available, it means its external to this ontology
                name=data.get("name"),
            )
            for prefix, identifier, data in _iter_obo_graph(graph=graph)
        }

        #: CURIEs to typedefs
        typedefs: Mapping[Tuple[str, str], TypeDef] = {
            (typedef.prefix, typedef.identifier): typedef
            for typedef in iterate_graph_typedefs(graph, ontology)
        }

        synonym_typedefs: Mapping[str, SynonymTypeDef] = {
            synonym_typedef.id: synonym_typedef
            for synonym_typedef in iterate_graph_synonym_typedefs(graph)
        }

        missing_typedefs = set()
        terms = []
        n_alt_ids, n_parents, n_synonyms, n_relations, n_properties = 0, 0, 0, 0, 0
        for prefix, identifier, data in _iter_obo_graph(graph=graph):
            if prefix != ontology or not data:
                continue

            reference = references[ontology, identifier]

            try:
                node_xrefs = list(iterate_node_xrefs(prefix=prefix, data=data, strict=strict))
            except MissingPrefix as e:
                e.reference = reference
                raise e
            xrefs, provenance = [], []
            for node_xref in node_xrefs:
                if node_xref.prefix in PROVENANCE_PREFIXES:
                    provenance.append(node_xref)
                else:
                    xrefs.append(node_xref)

            definition, definition_references = get_definition(
                data, prefix=prefix, identifier=identifier
            )
            if definition_references:
                provenance.extend(definition_references)

            try:
                alt_ids = list(iterate_node_alt_ids(data, strict=strict))
            except MissingPrefix as e:
                e.reference = reference
                raise e
            n_alt_ids += len(alt_ids)

            try:
                parents = list(
                    iterate_node_parents(
                        data,
                        prefix=prefix,
                        identifier=identifier,
                        strict=strict,
                    )
                )
            except MissingPrefix as e:
                e.reference = reference
                raise e
            n_parents += len(parents)

            synonyms = list(
                iterate_node_synonyms(
                    data,
                    synonym_typedefs,
                    prefix=prefix,
                    identifier=identifier,
                    strict=strict,
                )
            )
            n_synonyms += len(synonyms)

            term = Term(
                reference=reference,
                definition=definition,
                parents=parents,
                synonyms=synonyms,
                xrefs=xrefs,
                provenance=provenance,
                alt_ids=alt_ids,
            )

            try:
                relations_references = list(
                    iterate_node_relationships(
                        data,
                        prefix=ontology,
                        identifier=identifier,
                        strict=strict,
                    )
                )
            except MissingPrefix as e:
                e.reference = reference
                raise e
            for relation, reference in relations_references:
                if (relation.prefix, relation.identifier) in typedefs:
                    typedef = typedefs[relation.prefix, relation.identifier]
                elif (relation.prefix, relation.identifier) in default_typedefs:
                    typedef = default_typedefs[relation.prefix, relation.identifier]
                else:
                    if (relation.prefix, relation.identifier) not in missing_typedefs:
                        missing_typedefs.add((relation.prefix, relation.identifier))
                        logger.warning("[%s] has no typedef for %s", ontology, relation)
                        logger.debug("[%s] available typedefs: %s", ontology, set(typedefs))
                    continue
                n_relations += 1
                term.append_relationship(typedef, reference)
            for prop, value in iterate_node_properties(data):
                n_properties += 1
                term.append_property(prop, value)
            terms.append(term)

        logger.info(
            f"[{ontology}] got {len(references)} references, {len(typedefs)} typedefs, {len(terms)} terms,"
            f" {n_alt_ids} alt ids, {n_parents} parents, {n_synonyms} synonyms,"
            f" {n_relations} relations, and {n_properties} properties",
        )

        return Obo(
            ontology=ontology,
            name=name,
            auto_generated_by=graph.graph.get("auto-generated-by"),
            format_version=graph.graph.get("format-version"),
            data_version=data_version,
            date=date,
            typedefs=list(typedefs.values()),
            synonym_typedefs=list(synonym_typedefs.values()),
            iter_terms=lambda: iter(terms),
        )

    def get_metadata(self) -> Mapping[str, Any]:
        """Get metadata."""
        return dict(
            version=self.data_version,
            date=self.date and self.date.isoformat(),
        )

    def iterate_id_name(self, *, use_tqdm: bool = False) -> Iterable[Tuple[str, str]]:
        """Iterate identifier name pairs."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"):
            if term.name:
                yield term.identifier, term.name

    def get_id_name_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, str]:
        """Get a mapping from identifiers to names."""
        return dict(self.iterate_id_name(use_tqdm=use_tqdm))

    def iterate_id_definition(self, *, use_tqdm: bool = False) -> Iterable[Tuple[str, str]]:
        """Iterate over pairs of terms' identifiers and their respective definitions."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"):
            if term.identifier and term.definition:
                yield term.identifier, term.definition

    def get_id_definition_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, str]:
        """Get a mapping from identifiers to definitions."""
        return dict(self.iterate_id_definition(use_tqdm=use_tqdm))

    ############
    # TYPEDEFS #
    ############

    def iterate_id_species(
        self, *, prefix: Optional[str] = None, use_tqdm: bool = False
    ) -> Iterable[Tuple[str, str]]:
        """Iterate over terms' identifiers and respective species (if available)."""
        if prefix is None:
            prefix = "ncbitaxon"
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting species"):
            species = term.get_species(prefix=prefix)
            if species:
                yield term.identifier, species.identifier

    def get_id_species_mapping(
        self, *, prefix: Optional[str] = None, use_tqdm: bool = False
    ) -> Mapping[str, str]:
        """Get a mapping from identifiers to species."""
        return dict(self.iterate_id_species(prefix=prefix, use_tqdm=use_tqdm))

    ############
    # TYPEDEFS #
    ############

    def get_typedef_df(self, use_tqdm: bool = False) -> pd.DataFrame:
        """Get a typedef dataframe."""
        rows = [
            (typedef.prefix, typedef.identifier, typedef.name)
            for typedef in tqdm(self.typedefs, disable=not use_tqdm)
        ]
        return pd.DataFrame(rows, columns=["prefix", "identifier", "name"])

    def iter_typedef_id_name(self) -> Iterable[Tuple[str, str]]:
        """Iterate over typedefs' identifiers and their respective names."""
        for typedef in self.typedefs:
            yield typedef.identifier, typedef.name

    def get_typedef_id_name_mapping(self) -> Mapping[str, str]:
        """Get a mapping from typedefs' identifiers to names."""
        return dict(self.iter_typedef_id_name())

    #########
    # PROPS #
    #########

    def iterate_properties(self, *, use_tqdm: bool = False) -> Iterable[Tuple[Term, str, str]]:
        """Iterate over tuples of terms, properties, and their values."""
        # TODO if property_prefix is set, try removing that as a prefix from all prop strings.
        for term in self._iter_terms(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting properties"
        ):
            for prop, value in term.iterate_properties():
                yield term, prop, value

    @property
    def properties_header(self):
        """Property dataframe header."""  # noqa:D401
        return [f"{self.ontology}_id", "property", "value"]

    def iter_property_rows(self, *, use_tqdm: bool = False) -> Iterable[Tuple[str, str, str]]:
        """Iterate property rows."""
        for term, prop, value in self.iterate_properties(use_tqdm=use_tqdm):
            yield term.identifier, prop, value

    def get_properties_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get all properties as a dataframe."""
        return pd.DataFrame(
            list(self.iter_property_rows(use_tqdm=use_tqdm)),
            columns=self.properties_header,
        )

    def iterate_filtered_properties(
        self, prop: str, *, use_tqdm: bool = False
    ) -> Iterable[Tuple[Term, str]]:
        """Iterate over tuples of terms and the values for the given property."""
        for term in self._iter_terms(use_tqdm=use_tqdm):
            for _prop, value in term.iterate_properties():
                if _prop == prop:
                    yield term, value

    def get_filtered_properties_df(self, prop: str, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get a dataframe of terms' identifiers to the given property's values."""
        return pd.DataFrame(
            list(self.get_filtered_properties_mapping(prop, use_tqdm=use_tqdm).items()),
            columns=[f"{self.ontology}_id", prop],
        )

    def get_filtered_properties_mapping(
        self, prop: str, *, use_tqdm: bool = False
    ) -> Mapping[str, str]:
        """Get a mapping from a term's identifier to the property.

        .. warning:: Assumes there's only one version of the property for each term.
        """
        return {
            term.identifier: value
            for term, value in self.iterate_filtered_properties(prop, use_tqdm=use_tqdm)
        }

    def get_filtered_properties_multimapping(
        self, prop: str, *, use_tqdm: bool = False
    ) -> Mapping[str, List[str]]:
        """Get a mapping from a term's identifier to the property values."""
        return multidict(
            (term.identifier, value)
            for term, value in self.iterate_filtered_properties(prop, use_tqdm=use_tqdm)
        )

    #############
    # RELATIONS #
    #############

    def iterate_relations(
        self, *, use_tqdm: bool = False
    ) -> Iterable[Tuple[Term, TypeDef, Reference]]:
        """Iterate over tuples of terms, relations, and their targets."""
        for term in self._iter_terms(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting relations"
        ):
            for parent in term.parents:
                yield term, is_a, parent
            for typedef, reference in term.iterate_relations():
                if (
                    typedef not in self.typedefs
                    and (typedef.prefix, typedef.identifier) not in default_typedefs
                ):
                    raise ValueError(f"Undefined typedef: {typedef.curie} ! {typedef.name}")
                yield term, typedef, reference

    def iter_relation_rows(
        self, use_tqdm: bool = False
    ) -> Iterable[Tuple[str, str, str, str, str, str]]:
        """Iterate the relations' rows."""
        for term, typedef, reference in self.iterate_relations(use_tqdm=use_tqdm):
            yield term.identifier, typedef.prefix, typedef.identifier, reference.prefix, reference.identifier

    def iterate_filtered_relations(
        self,
        relation: RelationHint,
        *,
        use_tqdm: bool = False,
    ) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over tuples of terms and ther targets for the given relation."""
        _target_prefix, _target_identifier = get_reference_tuple(relation)
        for term, typedef, reference in self.iterate_relations(use_tqdm=use_tqdm):
            if typedef.prefix == _target_prefix and typedef.identifier == _target_identifier:
                yield term, reference

    @property
    def relations_header(self) -> Sequence[str]:
        """Header for the relations dataframe."""  # noqa:D401
        return [f"{self.ontology}_id", RELATION_PREFIX, RELATION_ID, TARGET_PREFIX, TARGET_ID]

    def get_relations_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get all relations from the OBO."""
        return pd.DataFrame(
            list(self.iter_relation_rows(use_tqdm=use_tqdm)),
            columns=self.relations_header,
        )

    def get_filtered_relations_df(
        self,
        relation: RelationHint,
        *,
        use_tqdm: bool = False,
    ) -> pd.DataFrame:
        """Get a specific relation from OBO."""
        return pd.DataFrame(
            [
                (term.identifier, reference.prefix, reference.identifier)
                for term, reference in self.iterate_filtered_relations(relation, use_tqdm=use_tqdm)
            ],
            columns=[f"{self.ontology}_id", TARGET_PREFIX, TARGET_ID],
        )

    def iterate_filtered_relations_filtered_targets(
        self,
        relation: RelationHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over relationships between one identifier and another."""
        for term, reference in self.iterate_filtered_relations(
            relation=relation, use_tqdm=use_tqdm
        ):
            if reference.prefix == target_prefix:
                yield term, reference

    def get_relation_mapping(
        self,
        relation: RelationHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Mapping[str, str]:
        """Get a mapping from the term's identifier to the target's identifier.

        .. warning:: Assumes there's only one version of the property for each term.

         Example usage: get homology between HGNC and MGI:

        >>> from pyobo.sources.hgnc import get_obo
        >>> obo = get_obo()
        >>> human_mapt_hgnc_id = '6893'
        >>> mouse_mapt_mgi_id = '97180'
        >>> hgnc_mgi_orthology_mapping = obo.get_relation_mapping('ro:HOM0000017', 'mgi')
        >>> assert mouse_mapt_mgi_id == hgnc_mgi_orthology_mapping[human_mapt_hgnc_id]
        """
        return {
            term.identifier: reference.identifier
            for term, reference in self.iterate_filtered_relations_filtered_targets(
                relation=relation,
                target_prefix=target_prefix,
                use_tqdm=use_tqdm,
            )
        }

    def get_relation(
        self,
        source_identifier: str,
        relation: RelationHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Optional[str]:
        """Get the value for a bijective relation mapping between this resource and a target resource.

        >>> from pyobo.sources.hgnc import get_obo
        >>> obo = get_obo()
        >>> human_mapt_hgnc_id = '6893'
        >>> mouse_mapt_mgi_id = '97180'
        >>> assert mouse_mapt_mgi_id == obo.get_relation(human_mapt_hgnc_id, 'ro:HOM0000017', 'mgi')
        """
        relation_mapping = self.get_relation_mapping(
            relation=relation, target_prefix=target_prefix, use_tqdm=use_tqdm
        )
        return relation_mapping.get(source_identifier)

    def get_relation_multimapping(
        self,
        relation: RelationHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Mapping[str, List[str]]:
        """Get a mapping from the term's identifier to the target's identifiers."""
        return multidict(
            (term.identifier, reference.identifier)
            for term, reference in self.iterate_filtered_relations_filtered_targets(
                relation=relation,
                target_prefix=target_prefix,
                use_tqdm=use_tqdm,
            )
        )

    def get_id_multirelations_mapping(
        self,
        typedef: TypeDef,
        *,
        use_tqdm: bool = False,
    ) -> Mapping[str, List[Reference]]:
        """Get a mapping from identifiers to a list of all references for the given relation."""
        return multidict(
            (term.identifier, reference)
            for term in self._iter_terms(
                use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting {typedef.curie}"
            )
            for reference in term.get_relationships(typedef)
        )

    ############
    # SYNONYMS #
    ############

    def iterate_synonyms(self, *, use_tqdm: bool = False) -> Iterable[Tuple[Term, Synonym]]:
        """Iterate over pairs of term and synonym object."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting synonyms"):
            for synonym in sorted(term.synonyms, key=attrgetter("name")):
                yield term, synonym

    def iterate_synonym_rows(self, *, use_tqdm: bool = False) -> Iterable[Tuple[str, str]]:
        """Iterate over pairs of identifier and synonym text."""
        for term, synonym in self.iterate_synonyms(use_tqdm=use_tqdm):
            yield term.identifier, synonym.name

    def get_id_synonyms_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, List[str]]:
        """Get a mapping from identifiers to a list of sorted synonym strings."""
        return multidict(self.iterate_synonym_rows(use_tqdm=use_tqdm))

    #########
    # XREFS #
    #########

    def iterate_xrefs(self, *, use_tqdm: bool = False) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over xrefs."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting xrefs"):
            for xref in term.xrefs:
                yield term, xref

    def iterate_filtered_xrefs(
        self, prefix: str, *, use_tqdm: bool = False
    ) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over xrefs to a given prefix."""
        for term, xref in self.iterate_xrefs(use_tqdm=use_tqdm):
            if xref.prefix == prefix:
                yield term, xref

    def iterate_xref_rows(self, *, use_tqdm: bool = False) -> Iterable[Tuple[str, str, str]]:
        """Iterate over terms' identifiers, xref prefixes, and xref identifiers."""
        for term, xref in self.iterate_xrefs(use_tqdm=use_tqdm):
            yield term.identifier, xref.prefix, xref.identifier

    @property
    def xrefs_header(self):
        """The header for the xref dataframe."""  # noqa:D401
        return [f"{self.ontology}_id", TARGET_PREFIX, TARGET_ID]

    def get_xrefs_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get a dataframe of all xrefs extracted from the OBO document."""
        return pd.DataFrame(
            list(self.iterate_xref_rows(use_tqdm=use_tqdm)),
            columns=[f"{self.ontology}_id", TARGET_PREFIX, TARGET_ID],
        ).drop_duplicates()

    def get_filtered_xrefs_mapping(
        self, prefix: str, *, use_tqdm: bool = False
    ) -> Mapping[str, str]:
        """Get filtered xrefs as a dictionary."""
        return {
            term.identifier: xref.identifier
            for term, xref in self.iterate_filtered_xrefs(prefix, use_tqdm=use_tqdm)
        }

    def get_filtered_multixrefs_mapping(
        self, prefix: str, *, use_tqdm: bool = False
    ) -> Mapping[str, List[str]]:
        """Get filtered xrefs as a dictionary."""
        return multidict(
            (term.identifier, xref.identifier)
            for term, xref in self.iterate_filtered_xrefs(prefix, use_tqdm=use_tqdm)
        )

    ########
    # ALTS #
    ########

    def iterate_alts(self) -> Iterable[Tuple[Term, Reference]]:
        """Iterate over alternative identifiers."""
        for term in self:
            for alt in term.alt_ids:
                yield term, alt

    def iterate_alt_rows(self) -> Iterable[Tuple[str, str]]:
        """Iterate over pairs of terms' primary identifiers and alternate identifiers."""
        for term, alt in self.iterate_alts():
            yield term.identifier, alt.identifier

    def get_id_alts_mapping(self) -> Mapping[str, List[str]]:
        """Get a mapping from identifiers to a list of alternative identifiers."""
        return multidict((term.identifier, alt.identifier) for term, alt in self.iterate_alts())


def _clean_graph_ontology(graph, prefix: str) -> None:
    """Update the ontology entry in the graph's metadata, if necessary."""
    if "ontology" not in graph.graph:
        logger.warning('[%s] missing "ontology" key', prefix)
        graph.graph["ontology"] = prefix
    elif not graph.graph["ontology"].isalpha():
        logger.warning(
            "[%s] ontology=%s has a strange format. replacing with prefix",
            prefix,
            graph.graph["ontology"],
        )
        graph.graph["ontology"] = prefix


def _iter_obo_graph(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
) -> Iterable[Tuple[Optional[str], str, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in graph.nodes(data=True):
        prefix, identifier = normalize_curie(node, strict=strict)
        if prefix and identifier:
            yield prefix, identifier, data


def _convert_synonym_typedefs(synonym_typedefs: Iterable[SynonymTypeDef]) -> List[str]:
    """Convert the synonym type defs."""
    return [_convert_synonym_typedef(synonym_typedef) for synonym_typedef in synonym_typedefs]


def _convert_synonym_typedef(synonym_typedef: SynonymTypeDef) -> str:
    return f'{synonym_typedef.id} "{synonym_typedef.name}"'


def _convert_typedefs(typedefs: Iterable[TypeDef]) -> List[Mapping[str, Any]]:
    """Convert the type defs."""
    return [_convert_typedef(typedef) for typedef in typedefs]


def _convert_typedef(typedef: TypeDef) -> Mapping[str, Any]:
    """Convert a type def."""
    # TODO add more later
    return typedef.reference.to_dict()


def iterate_graph_synonym_typedefs(graph: nx.MultiDiGraph) -> Iterable[SynonymTypeDef]:
    """Get synonym type definitions from an :mod:`obonet` graph."""
    for s in graph.graph.get("synonymtypedef", []):
        sid, name = s.split(" ", 1)
        name = name.strip().strip('"')
        yield SynonymTypeDef(id=sid, name=name)


def iterate_graph_typedefs(
    graph: nx.MultiDiGraph, default_prefix: str, *, strict: bool = True
) -> Iterable[TypeDef]:
    """Get type definitions from an :mod:`obonet` graph."""
    for typedef in graph.graph.get("typedefs", []):
        if "id" in typedef:
            curie = typedef["id"]
        elif "identifier" in typedef:
            curie = typedef["identifier"]
        else:
            raise KeyError

        name = typedef.get("name")
        if name is None:
            logger.warning("[%s] typedef %s is missing a name", graph.graph["ontology"], curie)

        if ":" in curie:
            reference = Reference.from_curie(curie, name=name, strict=strict)
        else:
            reference = Reference(prefix=graph.graph["ontology"], identifier=curie, name=name)
        if reference is None:
            logger.warning("[%s] unable to parse typedef CURIE %s", graph.graph["ontology"], curie)
            continue

        xrefs = [Reference.from_curie(curie, strict=strict) for curie in typedef.get("xref", [])]
        yield TypeDef(reference=reference, xrefs=xrefs)


def get_definition(
    data, *, prefix: str, identifier: str
) -> Union[Tuple[None, None], Tuple[str, List[Reference]]]:
    definition = data.get("def")  # it's allowed not to have a definition
    if not definition:
        return None, None
    return _extract_definition(definition, prefix=prefix, identifier=identifier)


def _extract_definition(
    s: str,
    *,
    prefix: str,
    identifier: str,
    strict: bool = False,
) -> Union[Tuple[None, None], Tuple[str, List[Reference]]]:
    """Extract the definitions."""
    if not s.startswith('"'):
        raise ValueError("definition does not start with a quote")

    try:
        definition, rest = _quote_split(s)
    except ValueError:
        logger.warning("[%s:%s] could not parse definition: %s", prefix, identifier, s)
        return None, None

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning("[%s:%s] problem with definition: %s", prefix, identifier, s)
        provenance = []
    else:
        provenance = _parse_trailing_ref_list(rest, strict=strict)
    return definition, provenance


def _get_first_nonquoted(s: str) -> Optional[int]:
    for i, (a, b) in enumerate(pairwise(s), start=1):
        if b == '"' and a != "\\":
            return i


def _quote_split(s: str) -> Tuple[str, str]:
    s = s.lstrip('"')
    i = _get_first_nonquoted(s)
    if i is None:
        raise ValueError
    return _clean_definition(s[:i].strip()), s[i + 1 :].strip()


def _clean_definition(s: str) -> str:
    # if '\t' in s:
    #     logger.warning('has tab')
    return (
        s.replace('\\"', '"').replace("\n", " ").replace("\t", " ").replace("\d", "")  # noqa:W605
    )


def _extract_synonym(
    s: str,
    synonym_typedefs: Mapping[str, SynonymTypeDef],
    *,
    prefix: str,
    identifier: str,
    strict: bool = True,
) -> Optional[Synonym]:
    # TODO check if the synonym is written like a CURIE... it shouldn't but I've seen it happen
    try:
        name, rest = _quote_split(s)
    except ValueError:
        logger.warning("[%s:%s] invalid synonym: %s", prefix, identifier, s)
        return

    specificity = None
    for skos in "RELATED", "EXACT", "BROAD", "NARROW":
        if rest.startswith(skos):
            specificity = skos
            rest = rest[len(skos) :].strip()
            break

    stype = None
    if specificity is not None:  # go fishing for a synonym type definition
        for std in synonym_typedefs:
            if rest.startswith(std):
                stype = synonym_typedefs[std]
                rest = rest[len(std) :].strip()
                break

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning("[%s:%s] problem with synonym: %s", prefix, identifier, s)
        return

    provenance = _parse_trailing_ref_list(rest, strict=strict)
    return Synonym(name=name, specificity=specificity or "EXACT", type=stype, provenance=provenance)


def _parse_trailing_ref_list(rest, *, strict: bool = True):
    rest = rest.lstrip("[").rstrip("]")
    return [
        Reference.from_curie(curie.strip(), strict=strict)
        for curie in rest.split(",")
        if curie.strip()
    ]


def iterate_node_synonyms(
    data: Mapping[str, Any],
    synonym_typedefs: Mapping[str, SynonymTypeDef],
    *,
    prefix: str,
    identifier: str,
    strict: bool = False,
) -> Iterable[Synonym]:
    """Extract synonyms from a :mod:`obonet` node's data.

    Example strings:
    - "LTEC I" EXACT [Orphanet:93938,DOI:xxxx]
    - "LTEC I" EXACT [Orphanet:93938]
    - "LTEC I" [Orphanet:93938]
    - "LTEC I" []
    """
    for s in data.get("synonym", []):
        s = _extract_synonym(
            s, synonym_typedefs, prefix=prefix, identifier=identifier, strict=strict
        )
        if s is not None:
            yield s


HANDLED_PROPERTY_TYPES = {
    "xsd:string": str,
    "xsd:dateTime": datetime,
}


def iterate_node_properties(
    data: Mapping[str, Any],
    property_prefix: Optional[str] = None,
) -> Iterable[Tuple[str, str]]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get("property_value", []):
        prop, value_type = prop_value_type.split(" ", 1)
        if property_prefix is not None and prop.startswith(property_prefix):
            prop = prop[len(property_prefix) :]

        try:
            value, _ = value_type.rsplit(" ", 1)  # second entry is the value type
        except ValueError:
            # logger.debug(f'property missing datatype. defaulting to string - {prop_value_type}')
            value = value_type  # could assign type to be 'xsd:string' by default
        value = value.strip('"')
        yield prop, value


def iterate_node_parents(
    data: Mapping[str, Any],
    *,
    prefix: str,
    identifier: str,
    strict: bool = True,
) -> Iterable[Reference]:
    """Extract parents from a :mod:`obonet` node's data."""
    for parent_curie in data.get("is_a", []):
        reference = Reference.from_curie(parent_curie, strict=strict)
        if reference is None:
            logger.warning(
                "[%s:%s] could not parse parent curie: %s", prefix, identifier, parent_curie
            )
            continue
        yield reference


def iterate_node_alt_ids(data: Mapping[str, Any], *, strict: bool = True) -> Iterable[Reference]:
    """Extract alternate identifiers from a :mod:`obonet` node's data."""
    for curie in data.get("alt_id", []):
        reference = Reference.from_curie(curie, strict=strict)
        if reference is not None:
            yield reference


RELATION_REMAPPINGS = {
    "part_of": part_of.pair,
    "has_part": has_part.pair,
    "develops_from": develops_from.pair,
}


def iterate_node_relationships(
    data: Mapping[str, Any],
    *,
    prefix: str,
    identifier: str,
    strict: bool = True,
) -> Iterable[Tuple[Reference, Reference]]:
    """Extract relationships from a :mod:`obonet` node's data."""
    for s in data.get("relationship", []):
        relation_curie, target_curie = s.split(" ")
        if relation_curie in RELATION_REMAPPINGS:
            relation_prefix, relation_identifier = RELATION_REMAPPINGS[relation_curie]
        else:
            relation_prefix, relation_identifier = normalize_curie(relation_curie)
        if relation_prefix is not None and relation_identifier is not None:
            relation = Reference(prefix=relation_prefix, identifier=relation_identifier)
        elif prefix is not None:
            relation = Reference(prefix=prefix, identifier=relation_curie)
        else:
            relation = Reference.default(identifier=relation_curie)

        target = Reference.from_curie(target_curie, strict=strict)
        if target is None:
            logger.warning("[%s:%s] could not parse relation %s", prefix, identifier, s)
            continue

        yield relation, target


def iterate_node_xrefs(
    *, prefix: str, data: Mapping[str, Any], strict: bool = True
) -> Iterable[Reference]:
    """Extract xrefs from a :mod:`obonet` node's data."""
    for xref in data.get("xref", []):
        xref = xref.strip()

        if (
            any(xref.startswith(x) for x in get_xrefs_prefix_blacklist())
            or xref in get_xrefs_blacklist()
            or ":" not in xref
        ):
            continue  # sometimes xref to self... weird

        for blacklisted_prefix, new_prefix in get_remappings_prefix().items():
            if xref.startswith(blacklisted_prefix):
                xref = new_prefix + xref[len(blacklisted_prefix) :]

        split_space = " " in xref
        if split_space:
            _xref_split = xref.split(" ", 1)
            if _xref_split[1][0] not in {'"', "("}:
                logger.debug("[%s] Problem with space in xref %s", prefix, xref)
                continue
            xref = _xref_split[0]

        yv = Reference.from_curie(xref, strict=strict)
        if yv is not None:
            yield yv
