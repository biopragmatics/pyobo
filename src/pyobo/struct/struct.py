"""Data structures for OBO."""

import gzip
import json
import logging
import os
import sys
from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from textwrap import dedent
from typing import (
    Any,
    Callable,
    ClassVar,
    Optional,
    TextIO,
    Union,
)

import bioregistry
import click
import networkx as nx
import pandas as pd
from more_click import force_option, verbose_option
from tqdm.auto import tqdm
from typing_extensions import Literal

from .reference import Reference, Referenced
from .typedef import (
    RelationHint,
    TypeDef,
    comment,
    default_typedefs,
    exact_match,
    from_species,
    get_reference_tuple,
    has_ontology_root_term,
    has_part,
    is_a,
    orthologous,
    part_of,
    see_also,
    term_replaced_by,
)
from .utils import comma_separate, obo_escape_slim
from ..api.utils import get_version
from ..constants import (
    DATE_FORMAT,
    NCBITAXON_PREFIX,
    RELATION_ID,
    RELATION_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)
from ..identifier_utils import normalize_curie
from ..utils.io import multidict, write_iterable_tsv
from ..utils.misc import obo_to_owl
from ..utils.path import get_prefix_obo_path, prefix_directory_join

__all__ = [
    "Synonym",
    "SynonymTypeDef",
    "SynonymSpecificity",
    "SynonymSpecificities",
    "Term",
    "Obo",
    "make_ad_hoc_ontology",
    "abbreviation",
    "acronym",
]

logger = logging.getLogger(__name__)

SynonymSpecificity = Literal["EXACT", "NARROW", "BROAD", "RELATED"]
SynonymSpecificities: Sequence[SynonymSpecificity] = ("EXACT", "NARROW", "BROAD", "RELATED")


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: SynonymSpecificity = "EXACT"

    #: The type of synonym. Must be defined in OBO document!
    type: "SynonymTypeDef" = field(
        default_factory=lambda: DEFAULT_SYNONYM_TYPE  # type:ignore
    )

    #: References to articles where the synonym appears
    provenance: list[Reference] = field(default_factory=list)

    def to_obo(self) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f"synonym: {self._fp()}"

    def _fp(self) -> str:
        x = f'"{self._escape(self.name)}" {self.specificity}'
        if self.type and self.type.pair != DEFAULT_SYNONYM_TYPE.pair:
            x = f"{x} {self.type.preferred_curie}"
        return f"{x} [{comma_separate(self.provenance)}]"

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace('"', '\\"')


@dataclass
class SynonymTypeDef(Referenced):
    """A type definition for synonyms in OBO."""

    reference: Reference
    specificity: Optional[SynonymSpecificity] = None

    def to_obo(self) -> str:
        """Serialize to OBO."""
        rv = f'synonymtypedef: {self.preferred_curie} "{self.name}"'
        if self.specificity:
            rv = f"{rv} {self.specificity}"
        return rv

    @classmethod
    def from_text(
        cls,
        text: str,
        specificity: Optional[SynonymSpecificity] = None,
        *,
        lower: bool = True,
    ) -> "SynonymTypeDef":
        """Get a type definition from text that's normalized."""
        identifier = (
            text.replace("-", "_")
            .replace(" ", "_")
            .replace('"', "")
            .replace(")", "")
            .replace("(", "")
        )
        if lower:
            identifier = identifier.lower()
        return cls(
            reference=Reference(prefix="obo", identifier=identifier, name=text.replace('"', "")),
            specificity=specificity,
        )


DEFAULT_SYNONYM_TYPE = SynonymTypeDef(
    reference=Reference(prefix="oboInOwl", identifier="SynonymType", name="Synonym"),
)
abbreviation = SynonymTypeDef(
    reference=Reference(prefix="OMO", identifier="0003000", name="abbreviation")
)
acronym = SynonymTypeDef(reference=Reference(prefix="omo", identifier="0003012", name="acronym"))


ReferenceHint = Union[Reference, "Term", tuple[str, str], str]


def _ensure_ref(reference: ReferenceHint) -> Reference:
    if reference is None:
        raise ValueError("can not append null reference")
    if isinstance(reference, Term):
        return reference.reference
    if isinstance(reference, str):
        _rv = Reference.from_curie(reference)
        if _rv is None:
            raise ValueError(f"could not parse CURIE from {reference}")
        return _rv
    if isinstance(reference, tuple):
        return Reference(prefix=reference[0], identifier=reference[1])
    if isinstance(reference, Reference):
        return reference
    raise TypeError(f"invalid type given for a reference ({type(reference)}): {reference}")


@dataclass
class Term(Referenced):
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: Optional[str] = None

    #: References to articles in which the term appears
    provenance: list[Reference] = field(default_factory=list)

    #: Relationships defined by [Typedef] stanzas
    relationships: dict[TypeDef, list[Reference]] = field(default_factory=lambda: defaultdict(list))

    #: Properties, which are not defined with Typedef and have scalar values instead of references.
    properties: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: list[Reference] = field(default_factory=list)

    #: Synonyms of this term
    synonyms: list[Synonym] = field(default_factory=list)

    #: Equivalent references
    xrefs: list[Reference] = field(default_factory=list)
    xref_types: list[Reference] = field(default_factory=list)

    #: Alternate Identifiers
    alt_ids: list[Reference] = field(default_factory=list)

    #: The sub-namespace within the ontology
    namespace: Optional[str] = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: Optional[bool] = None

    type: Literal["Term", "Instance"] = "Term"

    def __hash__(self):
        return hash((self.__class__, self.prefix, self.identifier))

    @classmethod
    def from_triple(
        cls,
        prefix: str,
        identifier: str,
        name: Optional[str] = None,
        definition: Optional[str] = None,
        **kwargs,
    ) -> "Term":
        """Create a term from a reference."""
        return cls(
            reference=Reference(prefix=prefix, identifier=identifier, name=name),
            definition=definition,
            **kwargs,
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
        if prefix is None or identifier is None:
            raise ValueError
        return cls.from_triple(prefix=prefix, identifier=identifier, name=name)

    def append_provenance(self, reference: ReferenceHint) -> None:
        """Add a provenance reference."""
        self.provenance.append(_ensure_ref(reference))

    def append_synonym(
        self,
        synonym: Union[str, Synonym],
        *,
        type: Optional[SynonymTypeDef] = None,
        specificity: Optional[SynonymSpecificity] = None,
    ) -> None:
        """Add a synonym."""
        if isinstance(synonym, str):
            synonym = Synonym(
                synonym, type=type or DEFAULT_SYNONYM_TYPE, specificity=specificity or "EXACT"
            )
        self.synonyms.append(synonym)

    def append_alt(self, alt: Union[str, Reference]) -> None:
        """Add an alternative identifier."""
        if isinstance(alt, str):
            alt = Reference(prefix=self.prefix, identifier=alt)
        self.alt_ids.append(alt)

    def append_see_also(self, reference: ReferenceHint) -> "Term":
        """Add a see also relationship."""
        self.relationships[see_also].append(_ensure_ref(reference))
        return self

    def append_comment(self, value: str) -> "Term":
        """Add a comment relationship."""
        self.append_property(comment.curie, value)
        return self

    def append_replaced_by(self, reference: ReferenceHint) -> "Term":
        """Add a replaced by relationship."""
        self.append_relationship(term_replaced_by, reference)
        return self

    def append_parent(self, reference: ReferenceHint) -> "Term":
        """Add a parent to this entity."""
        reference = _ensure_ref(reference)
        if reference not in self.parents:
            self.parents.append(reference)
        return self

    def extend_parents(self, references: Collection[Reference]) -> None:
        """Add a collection of parents to this entity."""
        if any(x is None for x in references):
            raise ValueError("can not append a collection of parents containing a null parent")
        self.parents.extend(references)

    def get_properties(self, prop) -> list[str]:
        """Get properties from the given key."""
        return self.properties[prop]

    def get_property(self, prop) -> Optional[str]:
        """Get a single property of the given key."""
        r = self.get_properties(prop)
        if not r:
            return None
        if len(r) != 1:
            raise ValueError
        return r[0]

    def get_relationship(self, typedef: TypeDef) -> Optional[Reference]:
        """Get a single relationship of the given type."""
        r = self.get_relationships(typedef)
        if not r:
            return None
        if len(r) != 1:
            raise ValueError
        return r[0]

    def get_relationships(self, typedef: TypeDef) -> list[Reference]:
        """Get relationships from the given type."""
        return self.relationships[typedef]

    def append_exact_match(self, reference: ReferenceHint):
        """Append an exact match, also adding an xref."""
        reference = _ensure_ref(reference)
        self.append_relationship(exact_match, reference)
        self.append_xref(reference)
        return self

    def append_xref(self, reference: ReferenceHint) -> None:
        """Append an xref."""
        self.xrefs.append(_ensure_ref(reference))

    def append_relationship(self, typedef: TypeDef, reference: ReferenceHint) -> None:
        """Append a relationship."""
        self.relationships[typedef].append(_ensure_ref(reference))

    def set_species(self, identifier: str, name: Optional[str] = None):
        """Append the from_species relation."""
        if name is None:
            from pyobo.resources.ncbitaxon import get_ncbitaxon_name

            name = get_ncbitaxon_name(identifier)
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
        return None

    def extend_relationship(self, typedef: TypeDef, references: Iterable[Reference]) -> None:
        """Append several relationships."""
        if any(x is None for x in references):
            raise ValueError("can not extend a collection that includes a null reference")
        self.relationships[typedef].extend(references)

    def append_property(
        self, prop: Union[str, Reference, Referenced], value: Union[str, Reference, Referenced]
    ) -> None:
        """Append a property."""
        if isinstance(prop, (Reference, Referenced)):
            prop = prop.preferred_curie
        if isinstance(value, (Reference, Referenced)):
            value = value.preferred_curie
        self.properties[prop].append(value)

    def _definition_fp(self) -> str:
        if self.definition is None:
            raise AssertionError
        return f'"{obo_escape_slim(self.definition)}" [{comma_separate(self.provenance)}]'

    def iterate_relations(self) -> Iterable[tuple[TypeDef, Reference]]:
        """Iterate over pairs of typedefs and targets."""
        for typedef, targets in sorted(self.relationships.items(), key=_sort_relations):
            for target in sorted(targets, key=lambda ref: ref.preferred_curie):
                yield typedef, target

    def iterate_properties(self) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of property and values."""
        for prop, values in sorted(self.properties.items()):
            for value in sorted(values):
                yield prop, value

    def iterate_obo_lines(self, *, ontology, typedefs) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f"\n[{self.type}]"
        yield f"id: {self.preferred_curie}"
        if self.is_obsolete:
            yield "is_obsolete: true"
        if self.name:
            yield f"name: {obo_escape_slim(self.name)}"
        if self.namespace and self.namespace != "?":
            namespace_normalized = (
                self.namespace.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
            )
            yield f"namespace: {namespace_normalized}"

        if self.definition:
            yield f"def: {self._definition_fp()}"

        for xref in sorted(self.xrefs, key=attrgetter("prefix", "identifier")):
            yield f"xref: {xref}"  # __str__ bakes in the ! name

        parent_tag = "is_a" if self.type == "Term" else "instance_of"
        for parent in sorted(self.parents, key=attrgetter("prefix", "identifier")):
            yield f"{parent_tag}: {parent}"  # __str__ bakes in the ! name

        for typedef, references in sorted(self.relationships.items(), key=_sort_relations):
            if (not typedefs or typedef not in typedefs) and (
                ontology,
                typedef.curie,
            ) not in _TYPEDEF_WARNINGS:
                logger.warning(f"[{ontology}] typedef not defined in OBO: {typedef.curie}")
                _TYPEDEF_WARNINGS.add((ontology, typedef.curie))

            typedef_preferred_curie = typedef.preferred_curie
            for reference in sorted(references, key=attrgetter("prefix", "identifier")):
                s = f"relationship: {typedef_preferred_curie} {reference.preferred_curie}"
                if typedef.name or reference.name:
                    s += " !"
                if typedef.name:
                    s += f" {typedef.name}"
                if reference.name:
                    s += f" {reference.name}"
                yield s

        for prop, value in sorted(self.iterate_properties(), key=_sort_properties):
            # TODO deal with typedefs for properties
            yield f'property_value: {prop} "{value}" xsd:string'  # TODO deal with types later

        for synonym in sorted(self.synonyms, key=attrgetter("name")):
            yield synonym.to_obo()

    @staticmethod
    def _escape(s) -> str:
        return s.replace("\n", "\\n").replace('"', '\\"')


#: A set of warnings, used to make sure we don't show the same one over and over
_TYPEDEF_WARNINGS: set[tuple[str, str]] = set()


def _sort_relations(r):
    typedef, _references = r
    return typedef.preferred_curie


def _sort_properties(r):
    o = r[1]
    if isinstance(o, str):
        return o
    elif isinstance(o, Term):
        return o.curie
    else:
        raise TypeError(f"What {type(r)}: {r}")


class BioregistryError(ValueError):
    """An error raised for non-canonical prefixes."""

    def __str__(self) -> str:
        return dedent(
            f"""
        The value you gave for Obo.ontology field ({self.args[0]}) is not a canonical
        Bioregistry prefix in the Obo.ontology field.

        Please see https://bioregistry.io for valid prefixes or feel free to open an issue
        on the PyOBO issue tracker for support.
        """
        )


@dataclass
class Obo:
    """An OBO document."""

    #: The prefix for the ontology
    ontology: ClassVar[str]

    #: Should the prefix be validated against the Bioregistry?
    check_bioregistry_prefix: ClassVar[bool] = True

    #: The name of the ontology. If not given, tries looking up with the Bioregistry.
    name: ClassVar[Optional[str]] = None

    #: The OBO format
    format_version: ClassVar[str] = "1.2"

    #: Type definitions
    typedefs: ClassVar[Optional[list[TypeDef]]] = None

    #: Synonym type definitions
    synonym_typedefs: ClassVar[Optional[list[SynonymTypeDef]]] = None

    #: An annotation about how an ontology was generated
    auto_generated_by: ClassVar[Optional[str]] = None

    #: The idspaces used in the document
    idspaces: ClassVar[Optional[Mapping[str, str]]] = None

    #: For super-sized datasets that shouldn't be read into memory
    iter_only: ClassVar[bool] = False

    #: Set to true for resources that are unversioned/very dynamic, like MGI
    dynamic_version: ClassVar[bool] = False

    #: Set to a static version for the resource (i.e., the resource is not itself versioned)
    static_version: ClassVar[Optional[str]] = None

    bioversions_key: ClassVar[Optional[str]] = None

    #: Root terms to use for the ontology
    root_terms: ClassVar[Optional[list[Reference]]] = None

    #: The date the ontology was generated
    date: Optional[datetime] = field(default_factory=datetime.today)

    #: The ontology version
    data_version: Optional[str] = None

    #: Should this ontology be reloaded?
    force: bool = False

    #: The hierarchy of terms
    _hierarchy: Optional[nx.DiGraph] = field(init=False, default=None, repr=False)
    #: A cache of terms
    _items: Optional[list[Term]] = field(init=False, default=None, repr=False)

    term_sort_key: ClassVar[Optional[Callable[["Obo", Term], int]]] = None

    def __post_init__(self):
        """Run post-init checks."""
        if self.ontology is None:
            raise ValueError
        if self.check_bioregistry_prefix and self.ontology != bioregistry.normalize_prefix(
            self.ontology
        ):
            raise BioregistryError(self.ontology)
        # The type ignores are because of the hack where we override the
        # class variables in the instance
        if self.name is None:
            self.name = bioregistry.get_name(self.ontology)  # type:ignore
        if not self.data_version:
            if self.static_version:
                self.data_version = self.static_version
            else:
                self.data_version = self._get_version()
        if not self.dynamic_version:
            if self.data_version is None:
                raise ValueError(f"{self.ontology} is missing data_version")
            elif "/" in self.data_version:
                raise ValueError(f"{self.ontology} has a slash in version: {self.data_version}")
        if self.auto_generated_by is None:
            self.auto_generated_by = f"bio2obo:{self.ontology}"  # type:ignore

    def _get_version(self) -> Optional[str]:
        if self.bioversions_key:
            try:
                return get_version(self.bioversions_key)
            except KeyError:
                logger.warning(f"[{self.bioversions_key}] bioversions doesn't list this resource ")
            except OSError:
                logger.warning(f"[{self.bioversions_key}] error while looking up version")
        return None

    @property
    def _version_or_raise(self) -> str:
        if not self.data_version:
            raise ValueError(f"There is no version available for {self.ontology}")
        return self.data_version

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in this ontology."""
        raise NotImplementedError

    def get_graph(self):
        """Get an OBO Graph object."""
        from ..obographs import graph_from_obo

        return graph_from_obo(self)

    def write_obograph(self, path: Path) -> None:
        """Write OBO Graph json."""
        graph = self.get_graph()
        path.write_text(graph.model_dump_json(indent=2, exclude_none=True, exclude_unset=True))

    @classmethod
    def cli(cls) -> None:
        """Run the CLI for this class."""
        cli = cls.get_cls_cli()
        cli()

    @classmethod
    def get_cls_cli(cls) -> click.Command:
        """Get the CLI for this class."""

        @click.command()
        @verbose_option
        @force_option
        @click.option("--rewrite", "-r", is_flag=True)
        @click.option("--owl", is_flag=True, help="Write OWL via ROBOT")
        @click.option("--nodes", is_flag=True, help="Write nodes file")
        @click.option(
            "--version", help="Specify data version to get. Use this if bioversions is acting up."
        )
        def _main(force: bool, owl: bool, nodes: bool, version: Optional[str], rewrite: bool):
            try:
                inst = cls(force=force, data_version=version)
            except Exception as e:
                click.secho(f"[{cls.ontology}] Got an exception during instantiation - {type(e)}")
                sys.exit(1)

            try:
                inst.write_default(
                    write_obograph=True,
                    write_obo=True,
                    write_owl=owl,
                    write_nodes=nodes,
                    force=force or rewrite,
                    use_tqdm=True,
                )
            except Exception as e:
                click.secho(f"[{cls.ontology}] Got an exception during OBO writing {type(e)}")
                sys.exit(1)

        return _main

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return (self.date if self.date else datetime.now()).strftime(DATE_FORMAT)

    def _iter_terms(self, use_tqdm: bool = False, desc: str = "terms") -> Iterable[Term]:
        if use_tqdm:
            total: Optional[int]
            try:
                total = len(self._items_accessor)
            except TypeError:
                total = None
            yield from tqdm(self, desc=desc, unit_scale=True, unit="term", total=total)
        else:
            yield from self

    def iterate_obo_lines(self) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f"format-version: {self.format_version}"

        if self.auto_generated_by is not None:
            yield f"auto-generated-by: {self.auto_generated_by}"

        if self.data_version is not None:
            yield f"data-version: {self.data_version}"
        else:
            yield f"date: {self.date_formatted}"

        for prefix, url in sorted((self.idspaces or {}).items()):
            yield f"idspace: {prefix} {url}"

        for synonym_typedef in sorted((self.synonym_typedefs or []), key=attrgetter("curie")):
            if synonym_typedef.curie == DEFAULT_SYNONYM_TYPE.curie:
                continue
            yield synonym_typedef.to_obo()

        yield f"ontology: {self.ontology}"

        if self.name is None:
            raise ValueError("ontology is missing name")
        yield f'property_value: http://purl.org/dc/elements/1.1/title "{self.name}" xsd:string'
        license_spdx_id = bioregistry.get_license(self.ontology)
        if license_spdx_id:
            # TODO add SPDX to idspaces and use as a CURIE?
            yield f'property_value: http://purl.org/dc/terms/license "{license_spdx_id}" xsd:string'
        description = bioregistry.get_description(self.ontology)
        if description:
            description = obo_escape_slim(description.strip())
            yield f'property_value: http://purl.org/dc/elements/1.1/description "{description}" xsd:string'

        for root_term in self.root_terms or []:
            yield f"property_value: {has_ontology_root_term.preferred_curie} {root_term.preferred_curie}"

        for typedef in sorted(self.typedefs or [], key=attrgetter("curie")):
            yield from typedef.iterate_obo_lines()

        for term in self:
            yield from term.iterate_obo_lines(ontology=self.ontology, typedefs=self.typedefs)

    def write_obo(
        self, file: Union[None, str, TextIO, Path] = None, use_tqdm: bool = False
    ) -> None:
        """Write the OBO to a file."""
        it = self.iterate_obo_lines()
        if use_tqdm:
            it = tqdm(it, desc=f"Writing {self.ontology}", unit_scale=True, unit="line")
        if isinstance(file, (str, Path, os.PathLike)):
            with open(file, "w") as fh:
                self._write_lines(it, fh)
        else:
            self._write_lines(it, file)

    @staticmethod
    def _write_lines(it, file: Optional[TextIO]):
        for line in it:
            print(line, file=file)

    def write_obonet_gz(self, path: Union[str, Path]) -> None:
        """Write the OBO to a gzipped dump in Obonet JSON."""
        graph = self.to_obonet()
        with gzip.open(path, "wt") as file:
            json.dump(nx.node_link_data(graph), file)

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
    def _obograph_path(self) -> Path:
        return self._path(name=f"{self.ontology}.json")

    @property
    def _owl_path(self) -> Path:
        return self._path(name=f"{self.ontology}.owl")

    @property
    def _obonet_gz_path(self) -> Path:
        return self._path(name=f"{self.ontology}.obonet.json.gz")

    @property
    def _nodes_path(self) -> Path:
        return self._path(name=f"{self.ontology}.nodes.tsv")

    def write_default(
        self,
        use_tqdm: bool = False,
        force: bool = False,
        write_obo: bool = False,
        write_obonet: bool = False,
        write_obograph: bool = False,
        write_owl: bool = False,
        write_nodes: bool = False,
    ) -> None:
        """Write the OBO to the default path."""
        metadata = self.get_metadata()
        for path in (self._root_metadata_path, self._versioned_metadata_path):
            logger.debug("[%s v%s] caching metadata to %s", self.ontology, self.data_version, path)
            with path.open("w") as file:
                json.dump(metadata, file, indent=2)

        logger.debug(
            "[%s v%s] caching typedefs to %s", self.ontology, self.data_version, self._typedefs_path
        )
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
            logger.debug("[%s v%s] caching %s to %s", self.ontology, self.data_version, label, path)
            write_iterable_tsv(
                path=path,
                header=header,
                it=fn(),  # type:ignore
            )

        for relation in (is_a, has_part, part_of, from_species, orthologous):
            if relation is not is_a and self.typedefs is not None and relation not in self.typedefs:
                continue
            relations_path = self._cache("relations", name=f"{relation.curie}.tsv")
            if relations_path.exists() and not force:
                continue
            logger.debug(
                "[%s v%s] caching relation %s ! %s",
                self.ontology,
                self.data_version,
                relation.curie,
                relation.name,
            )
            relation_df = self.get_filtered_relations_df(relation)
            if not len(relation_df.index):
                continue
            relation_df.sort_values(list(relation_df.columns), inplace=True)
            relation_df.to_csv(relations_path, sep="\t", index=False)

        if (write_obo or write_owl) and (not self._obo_path.exists() or force):
            self.write_obo(self._obo_path, use_tqdm=use_tqdm)
        if write_obograph and (not self._obograph_path.exists() or force):
            self.write_obograph(self._obograph_path)
        if write_owl and (not self._owl_path.exists() or force):
            obo_to_owl(self._obo_path, self._owl_path)
        if write_obonet and (not self._obonet_gz_path.exists() or force):
            logger.debug("writing obonet to %s", self._obonet_gz_path)
            self.write_obonet_gz(self._obonet_gz_path)
        if write_nodes:
            self.get_graph().get_nodes_df().to_csv(self._nodes_path, sep="\t", index=False)

    @property
    def _items_accessor(self):
        if self._items is None:
            key = self.term_sort_key or attrgetter("curie")
            self._items = sorted(self.iter_terms(force=self.force), key=key)
        return self._items

    def __iter__(self) -> Iterator["Term"]:
        if self.iter_only:
            return iter(self.iter_terms(force=self.force))
        return iter(self._items_accessor)

    def ancestors(self, identifier: str) -> set[str]:
        """Return a set of identifiers for parents of the given identifier."""
        return nx.descendants(self.hierarchy, identifier)  # note this is backwards

    def descendants(self, identifier: str) -> set[str]:
        """Return a set of identifiers for the children of the given identifier."""
        return nx.ancestors(self.hierarchy, identifier)  # note this is backwards

    def is_descendant(self, descendant: str, ancestor: str) -> bool:
        """Return if the given identifier is a descendent of the ancestor.

        .. code-block:: python

            from pyobo import get_obo

            obo = get_obo("go")

            interleukin_10_complex = "1905571"  # interleukin-10 receptor complex
            all_complexes = "0032991"
            assert obo.is_descendant("1905571", "0032991")
        """
        return ancestor in self.ancestors(descendant)

    @property
    def hierarchy(self) -> nx.DiGraph:
        """A graph representing the parent/child relationships between the entities.

        To get all children of a given entity, do:

        .. code-block:: python

            from pyobo import get_obo

            obo = get_obo("go")

            identifier = "1905571"  # interleukin-10 receptor complex
            is_complex = "0032991" in nx.descendants(obo.hierarchy, identifier)  # should be true
        """
        if self._hierarchy is None:
            self._hierarchy = nx.DiGraph()
            for term in self._iter_terms(desc=f"[{self.ontology}] getting hierarchy"):
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
        for _source, _key, _target in links:
            rv.add_edge(_source, _target, key=_key)

        logger.info(
            "[%s v%s] exported graph with %d nodes",
            self.ontology,
            self.data_version,
            rv.number_of_nodes(),
        )
        return rv

    def get_metadata(self) -> Mapping[str, Any]:
        """Get metadata."""
        return {
            "version": self.data_version,
            "date": self.date and self.date.isoformat(),
        }

    def iterate_ids(self, *, use_tqdm: bool = False) -> Iterable[str]:
        """Iterate over identifiers."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"):
            if term.prefix == self.ontology:
                yield term.identifier

    def get_ids(self, *, use_tqdm: bool = False) -> set[str]:
        """Get the set of identifiers."""
        return set(self.iterate_ids(use_tqdm=use_tqdm))

    def iterate_id_name(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate identifier name pairs."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"):
            if term.prefix == self.ontology and term.name:
                yield term.identifier, term.name

    def get_id_name_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, str]:
        """Get a mapping from identifiers to names."""
        return dict(self.iterate_id_name(use_tqdm=use_tqdm))

    def iterate_id_definition(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of terms' identifiers and their respective definitions."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"):
            if term.identifier and term.definition:
                yield (
                    term.identifier,
                    term.definition.strip('"')
                    .replace("\n", " ")
                    .replace("\t", " ")
                    .replace("  ", " "),
                )

    def get_id_definition_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, str]:
        """Get a mapping from identifiers to definitions."""
        return dict(self.iterate_id_definition(use_tqdm=use_tqdm))

    def get_obsolete(self, *, use_tqdm: bool = False) -> set[str]:
        """Get the set of obsolete identifiers."""
        return {
            term.identifier
            for term in self._iter_terms(
                use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting obsolete"
            )
            if term.identifier and term.is_obsolete
        }

    ############
    # TYPEDEFS #
    ############

    def iterate_id_species(
        self, *, prefix: Optional[str] = None, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str]]:
        """Iterate over terms' identifiers and respective species (if available)."""
        if prefix is None:
            prefix = NCBITAXON_PREFIX
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
            for typedef in tqdm(self.typedefs or [], disable=not use_tqdm)
        ]
        return pd.DataFrame(rows, columns=["prefix", "identifier", "name"])

    def iter_typedef_id_name(self) -> Iterable[tuple[str, str]]:
        """Iterate over typedefs' identifiers and their respective names."""
        for typedef in self.typedefs or []:
            yield typedef.identifier, typedef.name

    def get_typedef_id_name_mapping(self) -> Mapping[str, str]:
        """Get a mapping from typedefs' identifiers to names."""
        return dict(self.iter_typedef_id_name())

    #########
    # PROPS #
    #########

    def iterate_properties(self, *, use_tqdm: bool = False) -> Iterable[tuple[Term, str, str]]:
        """Iterate over tuples of terms, properties, and their values."""
        # TODO if property_prefix is set, try removing that as a prefix from all prop strings.
        for term in self._iter_terms(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting properties"
        ):
            for prop, value in term.iterate_properties():
                yield term, prop, value

    @property
    def properties_header(self):
        """Property dataframe header."""
        return [f"{self.ontology}_id", "property", "value"]

    def iter_property_rows(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str, str]]:
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
    ) -> Iterable[tuple[Term, str]]:
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
    ) -> Mapping[str, list[str]]:
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
    ) -> Iterable[tuple[Term, TypeDef, Reference]]:
        """Iterate over tuples of terms, relations, and their targets."""
        for term in self._iter_terms(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting relations"
        ):
            for parent in term.parents:
                yield term, is_a, parent
            for typedef, reference in term.iterate_relations():
                if (self.typedefs is None or typedef not in self.typedefs) and (
                    typedef.prefix,
                    typedef.identifier,
                ) not in default_typedefs:
                    raise ValueError(f"Undefined typedef: {typedef.curie} ! {typedef.name}")
                yield term, typedef, reference

    def iter_relation_rows(
        self, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str, str, str, str]]:
        """Iterate the relations' rows."""
        for term, typedef, reference in self.iterate_relations(use_tqdm=use_tqdm):
            yield (
                term.identifier,
                typedef.prefix,
                typedef.identifier,
                reference.prefix,
                reference.identifier,
            )

    def iterate_filtered_relations(
        self,
        relation: RelationHint,
        *,
        use_tqdm: bool = False,
    ) -> Iterable[tuple[Term, Reference]]:
        """Iterate over tuples of terms and ther targets for the given relation."""
        _target_prefix, _target_identifier = get_reference_tuple(relation)
        for term, typedef, reference in self.iterate_relations(use_tqdm=use_tqdm):
            if typedef.prefix == _target_prefix and typedef.identifier == _target_identifier:
                yield term, reference

    @property
    def relations_header(self) -> Sequence[str]:
        """Header for the relations dataframe."""
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
    ) -> Iterable[tuple[Term, Reference]]:
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
        >>> human_mapt_hgnc_id = "6893"
        >>> mouse_mapt_mgi_id = "97180"
        >>> hgnc_mgi_orthology_mapping = obo.get_relation_mapping("ro:HOM0000017", "mgi")
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
        >>> human_mapt_hgnc_id = "6893"
        >>> mouse_mapt_mgi_id = "97180"
        >>> assert mouse_mapt_mgi_id == obo.get_relation(human_mapt_hgnc_id, "ro:HOM0000017", "mgi")
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
    ) -> Mapping[str, list[str]]:
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
    ) -> Mapping[str, list[Reference]]:
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

    def iterate_synonyms(self, *, use_tqdm: bool = False) -> Iterable[tuple[Term, Synonym]]:
        """Iterate over pairs of term and synonym object."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting synonyms"):
            for synonym in sorted(term.synonyms, key=attrgetter("name")):
                yield term, synonym

    def iterate_synonym_rows(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of identifier and synonym text."""
        for term, synonym in self.iterate_synonyms(use_tqdm=use_tqdm):
            yield term.identifier, synonym.name

    def get_id_synonyms_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, list[str]]:
        """Get a mapping from identifiers to a list of sorted synonym strings."""
        return multidict(self.iterate_synonym_rows(use_tqdm=use_tqdm))

    #########
    # XREFS #
    #########

    def iterate_xrefs(self, *, use_tqdm: bool = False) -> Iterable[tuple[Term, Reference]]:
        """Iterate over xrefs."""
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting xrefs"):
            for xref in term.xrefs:
                yield term, xref

    def iterate_filtered_xrefs(
        self, prefix: str, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Term, Reference]]:
        """Iterate over xrefs to a given prefix."""
        for term, xref in self.iterate_xrefs(use_tqdm=use_tqdm):
            if xref.prefix == prefix:
                yield term, xref

    def iterate_xref_rows(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str, str]]:
        """Iterate over terms' identifiers, xref prefixes, and xref identifiers."""
        for term, xref in self.iterate_xrefs(use_tqdm=use_tqdm):
            yield term.identifier, xref.prefix, xref.identifier

    @property
    def xrefs_header(self):
        """The header for the xref dataframe."""
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
    ) -> Mapping[str, list[str]]:
        """Get filtered xrefs as a dictionary."""
        return multidict(
            (term.identifier, xref.identifier)
            for term, xref in self.iterate_filtered_xrefs(prefix, use_tqdm=use_tqdm)
        )

    ########
    # ALTS #
    ########

    def iterate_alts(self) -> Iterable[tuple[Term, Reference]]:
        """Iterate over alternative identifiers."""
        for term in self:
            for alt in term.alt_ids:
                yield term, alt

    def iterate_alt_rows(self) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of terms' primary identifiers and alternate identifiers."""
        for term, alt in self.iterate_alts():
            yield term.identifier, alt.identifier

    def get_id_alts_mapping(self) -> Mapping[str, list[str]]:
        """Get a mapping from identifiers to a list of alternative identifiers."""
        return multidict((term.identifier, alt.identifier) for term, alt in self.iterate_alts())


def make_ad_hoc_ontology(
    _ontology: str,
    _name: str,
    _auto_generated_by: Optional[str] = None,
    _format_version: str = "1.2",
    _typedefs: Optional[list[TypeDef]] = None,
    _synonym_typedefs: Optional[list[SynonymTypeDef]] = None,
    _date: Optional[datetime] = None,
    _data_version: Optional[str] = None,
    _idspaces: Optional[Mapping[str, str]] = None,
    _root_terms: Optional[list[Reference]] = None,
    *,
    terms: list[Term],
) -> "Obo":
    """Make an ad-hoc ontology."""

    class AdHocOntology(Obo):
        """An ad hoc ontology created from an OBO file."""

        ontology = _ontology
        name = _name
        auto_generated_by = _auto_generated_by
        format_version = _format_version
        typedefs = _typedefs
        synonym_typedefs = _synonym_typedefs
        idspaces = _idspaces
        root_terms = _root_terms

        def __post_init__(self):
            self.date = _date
            self.data_version = _data_version

        def iter_terms(self, force: bool = False) -> Iterable[Term]:
            """Iterate over terms in the ad hoc ontology."""
            return terms

    return AdHocOntology()


def _convert_typedefs(typedefs: Optional[Iterable[TypeDef]]) -> list[Mapping[str, Any]]:
    """Convert the type defs."""
    if not typedefs:
        return []
    return [_convert_typedef(typedef) for typedef in typedefs]


def _convert_typedef(typedef: TypeDef) -> Mapping[str, Any]:
    """Convert a type def."""
    # TODO add more later
    return typedef.reference.model_dump()


def _convert_synonym_typedefs(synonym_typedefs: Optional[Iterable[SynonymTypeDef]]) -> list[str]:
    """Convert the synonym type defs."""
    if not synonym_typedefs:
        return []
    return [_convert_synonym_typedef(synonym_typedef) for synonym_typedef in synonym_typedefs]


def _convert_synonym_typedef(synonym_typedef: SynonymTypeDef) -> str:
    return f'{synonym_typedef.preferred_curie} "{synonym_typedef.name}"'
