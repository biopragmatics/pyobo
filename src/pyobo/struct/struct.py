"""Data structures for OBO."""

from __future__ import annotations

import datetime
import itertools as itt
import json
import logging
import os
import sys
import warnings
from collections import ChainMap, defaultdict
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any, ClassVar, TextIO

import bioregistry
import click
import curies
import networkx as nx
import pandas as pd
import ssslm
from curies import Converter, ReferenceTuple
from curies import vocabulary as _cv
from more_click import force_option, verbose_option
from tqdm.auto import tqdm
from typing_extensions import Self

from . import vocabulary as v
from .reference import (
    OBOLiteral,
    Reference,
    Referenced,
    _reference_list_tag,
    comma_separate_references,
    default_reference,
    get_preferred_curie,
    reference_escape,
    reference_or_literal_to_str,
)
from .struct_utils import (
    Annotation,
    AnnotationsDict,
    HasReferencesMixin,
    IntersectionOfHint,
    PropertiesHint,
    ReferenceHint,
    RelationsHint,
    Stanza,
    StanzaType,
    UnionOfHint,
    _chain_tag,
    _ensure_ref,
    _get_prefixes_from_annotations,
    _get_references_from_annotations,
    _tag_property_targets,
)
from .utils import _boolean_tag, obo_escape_slim
from ..api.utils import get_version
from ..constants import (
    BUILD_SUBDIRECTORY_NAME,
    DATE_FORMAT,
    DEFAULT_PREFIX_MAP,
    NCBITAXON_PREFIX,
    RELATION_ID,
    RELATION_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)
from ..utils.cache import write_gzipped_graph
from ..utils.io import multidict, safe_open, write_iterable_tsv
from ..utils.path import (
    CacheArtifact,
    get_cache_path,
    get_relation_cache_path,
    prefix_directory_join,
)
from ..version import get_version as get_pyobo_version

__all__ = [
    "Obo",
    "Synonym",
    "SynonymTypeDef",
    "Term",
    "TypeDef",
    "abbreviation",
    "acronym",
    "make_ad_hoc_ontology",
]

logger = logging.getLogger(__name__)

#: Columns in the SSSOM dataframe
SSSOM_DF_COLUMNS = [
    "subject_id",
    "subject_label",
    "object_id",
    "predicate_id",
    "mapping_justification",
    "confidence",
    "contributor",
]
FORMAT_VERSION = "1.4"


@dataclass
class Synonym(HasReferencesMixin):
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: _cv.SynonymScope | None = None

    #: The type of synonym. Must be defined in OBO document!
    type: Reference | None = None

    #: References to articles where the synonym appears
    provenance: Sequence[Reference | OBOLiteral] = field(default_factory=list)

    #: Extra annotations
    annotations: list[Annotation] = field(default_factory=list)

    #: Language tag for the synonym
    language: str | None = None

    def __lt__(self, other: Synonym) -> bool:
        """Sort lexically by name."""
        return self._sort_key() < other._sort_key()

    def _get_references(self) -> defaultdict[str, set[Reference]]:
        """Get all prefixes used by the typedef."""
        rv: defaultdict[str, set[Reference]] = defaultdict(set)
        rv[v.has_dbxref.prefix].add(v.has_dbxref)
        if self.type is not None:
            rv[self.type.prefix].add(self.type)
        for provenance in self.provenance:
            match provenance:
                case Reference():
                    rv[provenance.prefix].add(provenance)
                case OBOLiteral(_, datatype, _language):
                    rv[datatype.prefix].add(v._c(datatype))
        for prefix, references in _get_references_from_annotations(self.annotations).items():
            rv[prefix].update(references)
        return rv

    def _sort_key(self) -> tuple[str, _cv.SynonymScope, str]:
        return (
            self.name,
            self.specificity or _cv.DEFAULT_SYNONYM_SCOPE,
            self.type.curie if self.type else "",
        )

    @property
    def predicate(self) -> curies.NamedReference:
        """Get the specificity reference."""
        return _cv.synonym_scopes[self.specificity or _cv.DEFAULT_SYNONYM_SCOPE]

    def to_obo(
        self,
        ontology_prefix: str,
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
    ) -> str:
        """Write this synonym as an OBO line to appear in a [Term] stanza."""
        return f"synonym: {self._fp(ontology_prefix, synonym_typedefs)}"

    def _fp(
        self,
        ontology_prefix: str,
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
    ) -> str:
        if synonym_typedefs is None:
            synonym_typedefs = {}

        x = f'"{self._escape(self.name)}"'

        # Add on the specificity, e.g., EXACT
        synonym_typedef = _synonym_typedef_warn(ontology_prefix, self.type, synonym_typedefs)
        if synonym_typedef is not None and synonym_typedef.specificity is not None:
            x = f"{x} {synonym_typedef.specificity}"
        elif self.specificity is not None:
            x = f"{x} {self.specificity}"
        elif self.type is not None:
            # it's not valid to have a synonym type without a specificity,
            # so automatically assign one if we'll need it
            x = f"{x} {_cv.DEFAULT_SYNONYM_SCOPE}"

        # Add on the synonym type, if exists
        if self.type is not None:
            x = f"{x} {reference_escape(self.type, ontology_prefix=ontology_prefix)}"

        # the provenance list is required, even if it's empty :/
        x = f"{x} [{comma_separate_references(self.provenance)}]"

        # OBO flat file format does not support language,
        # but at least we can mention it here as a comment
        if self.language:
            x += f" ! language: {self.language}"

        return x

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace('"', '\\"')


@dataclass
class SynonymTypeDef(Referenced, HasReferencesMixin):
    """A type definition for synonyms in OBO."""

    reference: Reference
    specificity: _cv.SynonymScope | None = None

    def __hash__(self) -> int:
        # have to re-define hash because of the @dataclass
        return hash((self.__class__, self.prefix, self.identifier))

    def to_obo(self, ontology_prefix: str) -> str:
        """Serialize to OBO."""
        rv = f"synonymtypedef: {reference_escape(self.reference, ontology_prefix=ontology_prefix)}"
        name = self.name or ""
        rv = f'{rv} "{name}"'
        if self.specificity:
            rv = f"{rv} {self.specificity}"
        return rv

    def _get_references(self) -> dict[str, set[Reference]]:
        """Get all references used by the typedef."""
        rv: defaultdict[str, set[Reference]] = defaultdict(set)
        rv[self.reference.prefix].add(self.reference)
        if self.specificity is not None:
            # weird syntax, but this just gets the synonym scope
            # predicate as a pyobo reference
            r = v._c(_cv.synonym_scopes[self.specificity])
            rv[r.prefix].add(r)
        return dict(rv)


DEFAULT_SYNONYM_TYPE = SynonymTypeDef(
    reference=Reference(prefix="oboInOwl", identifier="SynonymType", name="synonym type"),
)
abbreviation = SynonymTypeDef(
    reference=Reference(prefix="OMO", identifier="0003000", name="abbreviation")
)
acronym = SynonymTypeDef(reference=Reference(prefix="omo", identifier="0003012", name="acronym"))
uk_spelling = SynonymTypeDef(
    reference=Reference(prefix="omo", identifier="0003005", name="UK spelling synonym")
)
default_synonym_typedefs: dict[ReferenceTuple, SynonymTypeDef] = {
    abbreviation.pair: abbreviation,
    acronym.pair: acronym,
    uk_spelling.pair: uk_spelling,
}


@dataclass
class Term(Stanza):
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: str | None = None

    #: Object properties
    relationships: RelationsHint = field(default_factory=lambda: defaultdict(list))

    _axioms: AnnotationsDict = field(default_factory=lambda: defaultdict(list))

    properties: PropertiesHint = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: list[Reference] = field(default_factory=list)

    intersection_of: IntersectionOfHint = field(default_factory=list)
    union_of: UnionOfHint = field(default_factory=list)
    equivalent_to: list[Reference] = field(default_factory=list)
    disjoint_from: list[Reference] = field(default_factory=list)

    #: Synonyms of this term
    synonyms: list[Synonym] = field(default_factory=list)

    #: Database cross-references, see :func:`get_mappings` for
    #: access to all mappings in an SSSOM-like interface
    xrefs: list[Reference] = field(default_factory=list)

    #: The sub-namespace within the ontology
    namespace: str | None = None

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: bool | None = None

    type: StanzaType = "Term"

    builtin: bool | None = None
    is_anonymous: bool | None = None
    subsets: list[Reference] = field(default_factory=list)

    def __hash__(self) -> int:
        # have to re-define hash because of the @dataclass
        return hash((self.__class__, self.prefix, self.identifier))

    @classmethod
    def from_triple(
        cls,
        prefix: str,
        identifier: str,
        name: str | None = None,
        definition: str | None = None,
        **kwargs,
    ) -> Term:
        """Create a term from a reference."""
        return cls(
            reference=Reference(prefix=prefix, identifier=identifier, name=name),
            definition=definition,
            **kwargs,
        )

    @classmethod
    def default(cls, prefix, identifier, name=None) -> Self:
        """Create a default term."""
        return cls(reference=default_reference(prefix=prefix, identifier=identifier, name=name))

    def append_see_also_uri(self, uri: str) -> Self:
        """Add a see also property."""
        return self.annotate_uri(v.see_also, uri)

    def extend_parents(self, references: Collection[Reference]) -> None:
        """Add a collection of parents to this entity."""
        warnings.warn("use append_parent", DeprecationWarning, stacklevel=2)
        if any(x is None for x in references):
            raise ValueError("can not append a collection of parents containing a null parent")
        self.parents.extend(references)

    def get_property_literals(self, prop: ReferenceHint) -> list[str]:
        """Get properties from the given key."""
        return [reference_or_literal_to_str(t) for t in self.properties.get(_ensure_ref(prop), [])]

    def get_property(self, prop: ReferenceHint) -> str | None:
        """Get a single property of the given key."""
        r = self.get_property_literals(prop)
        if not r:
            return None
        if len(r) != 1:
            raise ValueError
        return r[0]

    def append_exact_match(
        self,
        reference: ReferenceHint,
        *,
        mapping_justification: Reference | None = None,
        confidence: float | None = None,
        contributor: Reference | None = None,
    ) -> Self:
        """Append an exact match, also adding an xref."""
        reference = _ensure_ref(reference)
        axioms = self._prepare_mapping_annotations(
            mapping_justification=mapping_justification,
            confidence=confidence,
            contributor=contributor,
        )
        self.annotate_object(v.exact_match, reference, annotations=axioms)
        return self

    def set_species(self, identifier: str, name: str | None = None) -> Self:
        """Append the from_species relation."""
        if name is None:
            from pyobo.resources.ncbitaxon import get_ncbitaxon_name

            name = get_ncbitaxon_name(identifier)
        return self.append_relationship(
            v.from_species, Reference(prefix=NCBITAXON_PREFIX, identifier=identifier, name=name)
        )

    def get_species(self, prefix: str = NCBITAXON_PREFIX) -> Reference | None:
        """Get the species if it exists.

        :param prefix: The prefix to use in case the term has several species annotations.
        """
        for species in self.get_relationships(v.from_species):
            if species.prefix == prefix:
                return species
        return None

    def extend_relationship(self, typedef: ReferenceHint, references: Iterable[Reference]) -> None:
        """Append several relationships."""
        warnings.warn("use append_relationship", DeprecationWarning, stacklevel=2)
        if any(x is None for x in references):
            raise ValueError("can not extend a collection that includes a null reference")
        typedef = _ensure_ref(typedef)
        self.relationships[typedef].extend(references)

    def iterate_obo_lines(
        self,
        *,
        ontology_prefix: str,
        typedefs: Mapping[ReferenceTuple, TypeDef],
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
        emit_object_properties: bool = True,
        emit_annotation_properties: bool = True,
    ) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file."""
        yield f"\n[{self.type}]"
        # 1
        yield f"id: {self._reference(self.reference, ontology_prefix)}"
        # 2
        yield from _boolean_tag("is_anonymous", self.is_anonymous)
        # 3
        if self.name:
            yield f"name: {obo_escape_slim(self.name)}"
        # 4
        if self.namespace and self.namespace != "?":
            namespace_normalized = (
                self.namespace.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
            )
            yield f"namespace: {namespace_normalized}"
        # 5
        for alt in sorted(self.alt_ids):
            yield f"alt_id: {self._reference(alt, ontology_prefix, add_name_comment=True)}"
        # 6
        if self.definition:
            yield f"def: {self._definition_fp()}"
        # 7
        for comment in self.get_comments():
            yield f'comment: "{comment}"'
        # 8
        yield from _reference_list_tag("subset", self.subsets, ontology_prefix)
        # 9
        for synonym in sorted(self.synonyms):
            yield synonym.to_obo(ontology_prefix=ontology_prefix, synonym_typedefs=synonym_typedefs)
        # 10
        yield from self._iterate_xref_obo(ontology_prefix=ontology_prefix)
        # 11
        yield from _boolean_tag("builtin", self.builtin)
        # 12
        if emit_annotation_properties:
            yield from self._iterate_obo_properties(
                ontology_prefix=ontology_prefix,
                skip_predicate_objects=v.SKIP_PROPERTY_PREDICATES_OBJECTS,
                skip_predicate_literals=v.SKIP_PROPERTY_PREDICATES_LITERAL,
                typedefs=typedefs,
            )
        # 13
        parent_tag = "is_a" if self.type == "Term" else "instance_of"
        yield from _reference_list_tag(parent_tag, self.parents, ontology_prefix)
        # 14
        yield from self._iterate_intersection_of_obo(ontology_prefix=ontology_prefix)
        # 15
        yield from _reference_list_tag("union_of", self.union_of, ontology_prefix=ontology_prefix)
        # 16
        yield from _reference_list_tag(
            "equivalent_to", self.equivalent_to, ontology_prefix=ontology_prefix
        )
        # 17
        yield from _reference_list_tag(
            "disjoint_from", self.disjoint_from, ontology_prefix=ontology_prefix
        )
        # 18
        if emit_object_properties:
            yield from self._iterate_obo_relations(
                ontology_prefix=ontology_prefix, typedefs=typedefs
            )
        # 19 TODO created_by
        # 20
        for x in self.get_property_values(v.obo_creation_date):
            if isinstance(x, OBOLiteral):
                yield f"creation_date: {x.value}"
        # 21
        yield from _boolean_tag("is_obsolete", self.is_obsolete)
        # 22
        yield from _tag_property_targets(
            "replaced_by", self, v.term_replaced_by, ontology_prefix=ontology_prefix
        )
        # 23
        yield from _tag_property_targets(
            "consider", self, v.see_also, ontology_prefix=ontology_prefix
        )


#: A set of warnings, used to make sure we don't show the same one over and over
_SYNONYM_TYPEDEF_WARNINGS: set[tuple[str, Reference]] = set()


def _synonym_typedef_warn(
    prefix: str,
    predicate: Reference | None,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
) -> SynonymTypeDef | None:
    if predicate is None or predicate.pair == DEFAULT_SYNONYM_TYPE.pair:
        return None
    if predicate.pair in default_synonym_typedefs:
        return default_synonym_typedefs[predicate.pair]
    if predicate.pair in synonym_typedefs:
        return synonym_typedefs[predicate.pair]
    key = prefix, predicate
    if key not in _SYNONYM_TYPEDEF_WARNINGS:
        _SYNONYM_TYPEDEF_WARNINGS.add(key)
        predicate_preferred_curie = get_preferred_curie(predicate)
        if predicate.prefix == "obo":
            # Throw our hands up in the air. By using `obo` as the prefix,
            # we already threw using "real" definitions out the window
            logger.warning(
                f"[{prefix}] synonym typedef with OBO prefix not defined: {predicate_preferred_curie}."
                f"\n\tThis might be because you used an unqualified prefix in an OBO file, "
                f"which automatically gets an OBO prefix."
            )
        else:
            logger.warning(f"[{prefix}] synonym typedef not defined: {predicate_preferred_curie}")
    return None


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


LOGGED_MISSING_URI: set[tuple[str, str]] = set()


@dataclass
class Obo:
    """An OBO document."""

    #: The prefix for the ontology
    ontology: ClassVar[str]

    #: Should the prefix be validated against the Bioregistry?
    check_bioregistry_prefix: ClassVar[bool] = True

    #: The name of the ontology. If not given, tries looking up with the Bioregistry.
    name: ClassVar[str | None] = None

    #: Type definitions
    typedefs: ClassVar[list[TypeDef] | None] = None

    #: Synonym type definitions
    synonym_typedefs: ClassVar[list[SynonymTypeDef] | None] = None

    #: An annotation about how an ontology was generated
    auto_generated_by: ClassVar[str | None] = None

    #: The idspaces used in the document
    idspaces: ClassVar[Mapping[str, str] | None] = None

    #: For super-sized datasets that shouldn't be read into memory
    iter_only: ClassVar[bool] = False

    #: Set to true for resources that are unversioned/very dynamic, like MGI
    dynamic_version: ClassVar[bool] = False

    #: Set to a static version for the resource (i.e., the resource is not itself versioned)
    static_version: ClassVar[str | None] = None

    bioversions_key: ClassVar[str | None] = None

    #: Root terms to use for the ontology
    root_terms: ClassVar[list[Reference] | None] = None

    #: The date the ontology was generated
    date: datetime.datetime | None = field(default_factory=datetime.datetime.today)

    #: The ontology version
    data_version: str | None = None

    #: Should this ontology be reloaded?
    force: bool = False

    #: The hierarchy of terms
    _hierarchy: nx.DiGraph | None = field(init=False, default=None, repr=False)
    #: A cache of terms
    _items: list[Term] | None = field(init=False, default=None, repr=False)

    subsetdefs: ClassVar[list[tuple[Reference, str]] | None] = None

    property_values: ClassVar[list[Annotation] | None] = None

    imports: ClassVar[list[str] | None] = None

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
            self.auto_generated_by = f"PyOBO v{get_pyobo_version(with_git_hash=True)} on {datetime.datetime.now().isoformat()}"  # type:ignore

    def _get_clean_idspaces(self) -> dict[str, str]:
        """Get normalized idspace dictionary."""
        rv = dict(
            ChainMap(
                # Add reasonable defaults, most of which are
                # mandated by the OWL spec anyway (except skos?)
                DEFAULT_PREFIX_MAP,
                dict(self.idspaces or {}),
                # automatically detect all prefixes in reference in the ontology,
                # then look up Bioregistry-approved URI prefixes
                self._infer_prefix_map(),
            )
        )
        return rv

    def _infer_prefix_map(self) -> dict[str, str]:
        """Get a prefix map including all prefixes used in the ontology."""
        rv = {}
        for prefix in sorted(self._get_prefixes(), key=str.casefold):
            resource = bioregistry.get_resource(prefix)
            if resource is None:
                raise ValueError
            uri_prefix = resource.get_rdf_uri_prefix()
            if uri_prefix is None:
                uri_prefix = resource.get_uri_prefix()
            if uri_prefix is None:
                # This allows us an escape hatch, since some
                # prefixes don't have an associated URI prefix
                uri_prefix = f"https://bioregistry.io/{prefix}:"
                if (self.ontology, prefix) not in LOGGED_MISSING_URI:
                    LOGGED_MISSING_URI.add((self.ontology, prefix))
                    logger.warning(
                        "[%s] uses prefix with no URI format: %s. Auto-generating Bioregistry link: %s",
                        self.ontology,
                        prefix,
                        uri_prefix,
                    )

            pp = bioregistry.get_preferred_prefix(prefix) or str(prefix)
            rv[pp] = uri_prefix
        return rv

    def _get_prefixes(self) -> set[str]:
        """Get all prefixes used by the ontology."""
        prefixes: set[str] = set(DEFAULT_PREFIX_MAP)
        for stanza in self._iter_stanzas():
            prefixes.update(stanza._get_prefixes())
        for synonym_typedef in self.synonym_typedefs or []:
            prefixes.update(synonym_typedef._get_prefixes())
        prefixes.update(subset.prefix for subset, _ in self.subsetdefs or [])
        # _iterate_property_pairs covers metadata, root terms,
        # and properties in self.property_values
        prefixes.update(_get_prefixes_from_annotations(self._iterate_property_pairs()))
        if self.auto_generated_by:
            prefixes.add("oboInOwl")
        return prefixes

    def _get_references(self) -> dict[str, set[Reference]]:
        """Get all references used by the ontology."""
        rv: defaultdict[str, set[Reference]] = defaultdict(set)

        for rr in itt.chain(self, self.typedefs or [], self.synonym_typedefs or []):
            for prefix, references in rr._get_references().items():
                rv[prefix].update(references)
        for subset, _ in self.subsetdefs or []:
            rv[subset.prefix].add(subset)
        # _iterate_property_pairs covers metadata, root terms,
        # and properties in self.property_values
        for prefix, references in _get_references_from_annotations(
            self._iterate_property_pairs()
        ).items():
            rv[prefix].update(references)
        if self.auto_generated_by:
            rv[v.obo_autogenerated_by.prefix].add(v.obo_autogenerated_by)
        return dict(rv)

    def _get_version(self) -> str | None:
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

    @property
    def _prefix_version(self) -> str:
        """Get the prefix and version (for logging)."""
        if self.data_version:
            return f"{self.ontology} {self.data_version}"
        return self.ontology

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in this ontology."""
        raise NotImplementedError

    def write_obograph(self, path: str | Path, *, converter: Converter | None = None) -> None:
        """Write OBO Graph json."""
        from . import obograph

        obograph.write_obograph(self, path, converter=converter)

    @classmethod
    def cli(cls, *args, default_rewrite: bool = False) -> Any:
        """Run the CLI for this class."""
        cli = cls.get_cls_cli(default_rewrite=default_rewrite)
        return cli(*args)

    @classmethod
    def get_cls_cli(cls, *, default_rewrite: bool = False) -> click.Command:
        """Get the CLI for this class."""

        @click.command()
        @verbose_option
        @force_option
        @click.option(
            "--rewrite/--no-rewrite",
            "-r",
            default=False,
            is_flag=True,
            help="Re-process the data, but don't download it again.",
        )
        @click.option("--owl", is_flag=True, help="Write OWL via ROBOT")
        @click.option("--ofn", is_flag=True, help="Write Functional OWL (OFN)")
        @click.option("--ttl", is_flag=True, help="Write turtle RDF via OFN")
        @click.option(
            "--version", help="Specify data version to get. Use this if bioversions is acting up."
        )
        def _main(force: bool, owl: bool, ofn: bool, ttl: bool, version: str | None, rewrite: bool):
            rewrite = True
            try:
                inst = cls(force=force, data_version=version)
            except Exception as e:
                click.secho(f"[{cls.ontology}] Got an exception during instantiation - {type(e)}")
                sys.exit(1)
            inst.write_default(
                write_obograph=False,
                write_obo=False,
                write_owl=owl,
                write_ofn=ofn,
                write_ttl=ttl,
                write_nodes=True,
                force=force or rewrite,
                use_tqdm=True,
            )

        return _main

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return (self.date if self.date else datetime.datetime.now()).strftime(DATE_FORMAT)

    def _iter_terms_safe(self) -> Iterator[Term]:
        if self.iter_only:
            return iter(self.iter_terms(force=self.force))
        return iter(self._items_accessor)

    def _iter_terms(self, use_tqdm: bool = False, desc: str = "terms") -> Iterable[Term]:
        yv = self._iter_terms_safe()
        if use_tqdm:
            total: int | None
            try:
                total = len(self._items_accessor)
            except TypeError:
                total = None
            yv = tqdm(yv, desc=desc, unit_scale=True, unit="term", total=total)
        yield from yv

    def _iter_stanzas(self, use_tqdm: bool = False, desc: str = "terms") -> Iterable[Stanza]:
        yield from self._iter_terms(use_tqdm=use_tqdm, desc=desc)
        yield from self.typedefs or []

    def iterate_obo_lines(
        self,
        emit_object_properties: bool = True,
        emit_annotation_properties: bool = True,
    ) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file.

        Here's the order:

        1. format-version (technically, this is the only required field)
        2. data-version
        3. date
        4. saved-by
        5. auto-generated-by
        6. import
        7. subsetdef
        8. synonymtypedef
        9. default-namespace
        10. namespace-id-rule
        11. idspace
        12. treat-xrefs-as-equivalent
        13. treat-xrefs-as-genus-differentia
        14. treat-xrefs-as-relationship
        15. treat-xrefs-as-is_a
        16. remark
        17. ontology
        """
        # 1
        yield f"format-version: {FORMAT_VERSION}"
        # 2
        if self.data_version:
            yield f"data-version: {self.data_version}"
        # 3
        if self.date:
            f"date: {self.date_formatted}"
        # 4 TODO saved-by
        # 5
        if self.auto_generated_by:
            yield f"auto-generated-by: {self.auto_generated_by}"
        # 6
        for imp in self.imports or []:
            yield f"import: {imp}"
        # 7
        for subset, subset_remark in self.subsetdefs or []:
            yield f'subsetdef: {reference_escape(subset, ontology_prefix=self.ontology)} "{subset_remark}"'
        # 8
        for synonym_typedef in sorted(self.synonym_typedefs or []):
            if synonym_typedef.curie == DEFAULT_SYNONYM_TYPE.curie:
                continue
            yield synonym_typedef.to_obo(ontology_prefix=self.ontology)
        # 9 TODO default-namespace
        # 10 TODO namespace-id-rule
        # 11
        for prefix, url in sorted(self._get_clean_idspaces().items()):
            if prefix in DEFAULT_PREFIX_MAP:
                # we don't need to write out the 4 default prefixes from
                # table 2 in https://www.w3.org/TR/owl2-syntax/#IRIs since
                # they're considered to always be builtin
                continue

            # additional assumptions about built in
            if prefix in {"obo", "oboInOwl"}:
                continue

            # ROBOT assumes that all OBO foundry prefixes are builtin,
            # so don't re-declare them
            if bioregistry.is_obo_foundry(prefix):
                continue

            yv = f"idspace: {prefix} {url}"
            if _yv_name := bioregistry.get_name(prefix):
                yv += f' "{_yv_name}"'
            yield yv
        # 12-15 are handled only during reading, and
        # PyOBO unmacros things before outputting
        # 12 treat-xrefs-as-equivalent
        # 13 treat-xrefs-as-genus-differentia
        # 14 treat-xrefs-as-relationship
        # 15 treat-xrefs-as-is_a
        # 16 TODO remark
        # 17
        yield f"ontology: {self.ontology}"
        # 18 (secret)
        yield from self._iterate_properties()

        typedefs = self._index_typedefs()
        synonym_typedefs = self._index_synonym_typedefs()

        # PROPERTIES
        for typedef in sorted(self.typedefs or []):
            yield from typedef.iterate_obo_lines(
                ontology_prefix=self.ontology,
                typedefs=typedefs,
                synonym_typedefs=synonym_typedefs,
            )

        # TERMS AND INSTANCES
        for term in self._iter_terms():
            yield from term.iterate_obo_lines(
                ontology_prefix=self.ontology,
                typedefs=typedefs,
                synonym_typedefs=synonym_typedefs,
                emit_object_properties=emit_object_properties,
                emit_annotation_properties=emit_annotation_properties,
            )

    def _iterate_properties(self) -> Iterable[str]:
        for predicate, value in self._iterate_property_pairs():
            match value:
                case OBOLiteral():
                    end = f'"{obo_escape_slim(value.value)}" {reference_escape(value.datatype, ontology_prefix=self.ontology)}'
                case Reference():
                    end = reference_escape(value, ontology_prefix=self.ontology)
            yield f"property_value: {reference_escape(predicate, ontology_prefix=self.ontology)} {end}"

    def _iterate_property_pairs(self) -> Iterable[Annotation]:
        # Title
        if self.name:
            yield Annotation(v.has_title, OBOLiteral.string(self.name))

        # License
        # TODO add SPDX to idspaces and use as a CURIE?
        if license_spdx_id := bioregistry.get_license(self.ontology):
            if license_spdx_id.startswith("http"):
                license_literal = OBOLiteral.uri(license_spdx_id)
            else:
                license_literal = OBOLiteral.string(license_spdx_id)
            yield Annotation(v.has_license, license_literal)

        # Description
        if description := bioregistry.get_description(self.ontology):
            description = obo_escape_slim(description.strip())
            yield Annotation(v.has_description, OBOLiteral.string(description.strip()))

        # Root terms
        for root_term in self.root_terms or []:
            yield Annotation(v.has_ontology_root_term, root_term)

        # Extras
        if self.property_values:
            yield from self.property_values

    def _index_typedefs(self) -> Mapping[ReferenceTuple, TypeDef]:
        from .typedef import default_typedefs

        return ChainMap(
            {t.pair: t for t in self.typedefs or []},
            default_typedefs,
        )

    def _index_synonym_typedefs(self) -> Mapping[ReferenceTuple, SynonymTypeDef]:
        return ChainMap(
            {t.pair: t for t in self.synonym_typedefs or []},
            default_synonym_typedefs,
        )

    def write_obo(
        self,
        file: None | str | TextIO | Path = None,
        *,
        use_tqdm: bool = False,
        emit_object_properties: bool = True,
        emit_annotation_properties: bool = True,
    ) -> None:
        """Write the OBO to a file."""
        it = self.iterate_obo_lines(
            emit_object_properties=emit_object_properties,
            emit_annotation_properties=emit_annotation_properties,
        )
        if use_tqdm:
            it = tqdm(
                it,
                desc=f"[{self._prefix_version}] writing OBO",
                unit_scale=True,
                unit="line",
            )
        if isinstance(file, str | Path | os.PathLike):
            with safe_open(file, read=False) as fh:
                self._write_lines(it, fh)
        else:
            self._write_lines(it, file)

    @staticmethod
    def _write_lines(it, file: TextIO | None):
        for line in it:
            print(line, file=file)

    def write_obonet_gz(self, path: str | Path) -> None:
        """Write the OBO to a gzipped dump in Obonet JSON."""
        graph = self.to_obonet()
        write_gzipped_graph(path=path, graph=graph)

    def write_ofn(self, path: str | Path) -> None:
        """Write as Functional OWL (OFN)."""
        from .functional.obo_to_functional import get_ofn_from_obo

        ofn = get_ofn_from_obo(self)
        ofn.write_funowl(path)

    def write_rdf(self, path: str | Path) -> None:
        """Write as Turtle RDF."""
        from .functional.obo_to_functional import get_ofn_from_obo

        ofn = get_ofn_from_obo(self)
        ofn.write_rdf(path)

    def write_nodes(self, path: str | Path) -> None:
        """Write a nodes TSV file."""
        write_iterable_tsv(
            path=path,
            header=self.nodes_header,
            it=self.iterate_edge_rows(),
        )

    @property
    def nodes_header(self) -> Sequence[str]:
        """Get the header for nodes."""
        return [
            "curie:ID",
            "name:string",
            "synonyms:string[]",
            "synonym_predicates:string[]",
            "synonym_types:string[]",
            "definition:string",
            "deprecated:boolean",
            "type:string",
            "provenance:string[]",
            "alts:string[]",
            "replaced_by:string[]",
            "mapping_objects:string[]",
            "mapping_predicates:string[]",
            "version:string",
        ]

    def _get_node_row(self, node: Term, sep: str, version: str) -> Sequence[str]:
        synonym_predicate_curies, synonym_type_curies, synonyms = [], [], []
        for synonym in node.synonyms:
            synonym_predicate_curies.append(synonym.predicate.curie)
            synonym_type_curies.append(synonym.type.curie if synonym.type else "")
            synonyms.append(synonym.name)
        mapping_predicate_curies, mapping_target_curies = [], []
        for predicate, obj in node.get_mappings(include_xrefs=True, add_context=False):
            mapping_predicate_curies.append(predicate.curie)
            mapping_target_curies.append(obj.curie)
        return (
            node.curie,
            node.name or "",
            sep.join(synonyms),
            sep.join(synonym_predicate_curies),
            sep.join(synonym_type_curies),
            node.definition or "",
            "true" if node.is_obsolete else "false",
            node.type,
            sep.join(
                reference.curie for reference in node.provenance if isinstance(reference, Reference)
            ),
            sep.join(alt_reference.curie for alt_reference in node.alt_ids),
            sep.join(ref.curie for ref in node.get_replaced_by()),
            sep.join(mapping_target_curies),
            sep.join(mapping_predicate_curies),
            version,
        )

    def iterate_node_rows(self, sep: str = ";") -> Iterable[Sequence[str]]:
        """Get a nodes iterator appropriate for serialization."""
        version = self.data_version or ""
        for node in self.iter_terms():
            if node.prefix != self.ontology:
                continue
            yield self._get_node_row(node, sep=sep, version=version)

    def write_edges(self, path: str | Path) -> None:
        """Write a edges TSV file."""
        # node, this is actually taken care of as part of the cache configuration
        write_iterable_tsv(
            path=path,
            header=self.edges_header,
            it=self.iterate_edge_rows(),
        )

    def _path(self, *parts: str, name: str | None = None) -> Path:
        return prefix_directory_join(self.ontology, *parts, name=name, version=self.data_version)

    def _get_cache_path(self, name: CacheArtifact) -> Path:
        return get_cache_path(self.ontology, name=name, version=self.data_version)

    @property
    def _root_metadata_path(self) -> Path:
        return prefix_directory_join(self.ontology, name="metadata.json")

    @property
    def _obo_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.obo.gz")

    @property
    def _obograph_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.json.gz")

    @property
    def _owl_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.owl.gz")

    @property
    def _obonet_gz_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.obonet.json.gz")

    @property
    def _ofn_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.ofn.gz")

    @property
    def _ttl_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.ttl")

    def _get_cache_config(self) -> list[tuple[CacheArtifact, Sequence[str], Callable]]:
        return [
            (CacheArtifact.names, [f"{self.ontology}_id", "name"], self.iterate_id_name),
            (
                CacheArtifact.definitions,
                [f"{self.ontology}_id", "definition"],
                self.iterate_id_definition,
            ),
            (
                CacheArtifact.species,
                [f"{self.ontology}_id", "taxonomy_id"],
                self.iterate_id_species,
            ),
            (CacheArtifact.alts, [f"{self.ontology}_id", "alt_id"], self.iterate_alt_rows),
            (CacheArtifact.mappings, SSSOM_DF_COLUMNS, self.iterate_mapping_rows),
            (CacheArtifact.relations, self.relations_header, self.iter_relation_rows),
            (CacheArtifact.edges, self.edges_header, self.iterate_edge_rows),
            (
                CacheArtifact.object_properties,
                self.object_properties_header,
                self.iter_object_properties,
            ),
            (
                CacheArtifact.literal_properties,
                self.literal_properties_header,
                self.iter_literal_properties,
            ),
            (
                CacheArtifact.literal_mappings,
                ssslm.LiteralMappingTuple._fields,
                self.iterate_literal_mapping_rows,
            ),
        ]

    def write_metadata(self) -> None:
        """Write the metadata JSON file."""
        metadata = self.get_metadata()
        for path in (self._root_metadata_path, self._get_cache_path(CacheArtifact.metadata)):
            logger.debug("[%s] caching metadata to %s", self._prefix_version, path)
            with safe_open(path, read=False) as file:
                json.dump(metadata, file, indent=2)

    def write_prefix_map(self) -> None:
        """Write a prefix map file that includes all prefixes used in this ontology."""
        with self._get_cache_path(CacheArtifact.prefixes).open("w") as file:
            json.dump(self._get_clean_idspaces(), file, indent=2)

    def write_cache(self, *, force: bool = False) -> None:
        """Write cache parts."""
        typedefs_path = self._get_cache_path(CacheArtifact.typedefs)
        logger.debug(
            "[%s] caching typedefs to %s",
            self._prefix_version,
            typedefs_path,
        )
        typedef_df: pd.DataFrame = self.get_typedef_df()
        typedef_df.sort_values(list(typedef_df.columns), inplace=True)
        typedef_df.to_csv(typedefs_path, sep="\t", index=False)

        for cache_artifact, header, fn in self._get_cache_config():
            path = self._get_cache_path(cache_artifact)
            if path.is_file() and not force:
                continue
            tqdm.write(
                f"[{self._prefix_version}] writing {cache_artifact.name} to {path}",
            )
            write_iterable_tsv(
                path=path,
                header=header,
                it=fn(),  # type:ignore
            )

        typedefs = self._index_typedefs()
        for relation in (v.is_a, v.has_part, v.part_of, v.from_species, v.orthologous):
            if relation is not v.is_a and relation.pair not in typedefs:
                continue
            relations_path = get_relation_cache_path(
                self.ontology, reference=relation, version=self.data_version
            )
            if relations_path.is_file() and not force:
                continue
            logger.debug(
                "[%s] caching relation %s ! %s",
                self._prefix_version,
                relation.curie,
                relation.name,
            )
            relation_df = self.get_filtered_relations_df(relation)
            if not len(relation_df.index):
                continue
            relation_df.sort_values(list(relation_df.columns), inplace=True)
            relation_df.to_csv(relations_path, sep="\t", index=False)

    def write_default(
        self,
        use_tqdm: bool = False,
        force: bool = False,
        write_obo: bool = False,
        write_obonet: bool = False,
        write_obograph: bool = False,
        write_owl: bool = False,
        write_ofn: bool = False,
        write_ttl: bool = False,
        write_nodes: bool = False,
        obograph_use_internal: bool = False,
        write_cache: bool = True,
    ) -> None:
        """Write the OBO to the default path."""
        self.write_metadata()
        self.write_prefix_map()
        if write_cache:
            self.write_cache(force=force)
        if write_obo and (not self._obo_path.is_file() or force):
            tqdm.write(f"[{self._prefix_version}] writing OBO to {self._obo_path}")
            self.write_obo(self._obo_path, use_tqdm=use_tqdm)
        if (write_ofn or write_owl or write_obograph) and (not self._ofn_path.is_file() or force):
            tqdm.write(f"[{self._prefix_version}] writing OFN to {self._ofn_path}")
            self.write_ofn(self._ofn_path)
        if write_obograph and (not self._obograph_path.is_file() or force):
            if obograph_use_internal:
                tqdm.write(f"[{self._prefix_version}] writing OBO Graph to {self._obograph_path}")
                self.write_obograph(self._obograph_path)
            else:
                import bioontologies.robot

                tqdm.write(
                    f"[{self.ontology}] converting OFN to OBO Graph at {self._obograph_path}"
                )
                bioontologies.robot.convert(
                    self._ofn_path, self._obograph_path, debug=True, merge=False, reason=False
                )
        if write_owl and (not self._owl_path.is_file() or force):
            tqdm.write(f"[{self._prefix_version}] writing OWL to {self._owl_path}")
            import bioontologies.robot

            bioontologies.robot.convert(
                self._ofn_path, self._owl_path, debug=True, merge=False, reason=False
            )
        if write_ttl and (not self._ttl_path.is_file() or force):
            tqdm.write(f"[{self._prefix_version}] writing Turtle to {self._ttl_path}")
            self.write_rdf(self._ttl_path)
        if write_obonet and (not self._obonet_gz_path.is_file() or force):
            tqdm.write(f"[{self._prefix_version}] writing obonet to {self._obonet_gz_path}")
            self.write_obonet_gz(self._obonet_gz_path)
        if write_nodes:
            nodes_path = self._get_cache_path(CacheArtifact.nodes)
            tqdm.write(f"[{self._prefix_version}] writing nodes TSV to {nodes_path}")
            self.write_nodes(nodes_path)

    @property
    def _items_accessor(self) -> list[Term]:
        if self._items is None:
            # if the term sort key is None, then the terms get sorted by their reference
            self._items = sorted(
                self.iter_terms(force=self.force),
            )
        return self._items

    def __iter__(self) -> Iterator[Term]:
        yield from self._iter_terms_safe()

    def ancestors(self, identifier: str) -> set[str]:
        """Return a set of identifiers for parents of the given identifier."""
        # FIXME switch to references
        return nx.descendants(self.hierarchy, identifier)  # note this is backwards

    def descendants(self, identifier: str) -> set[str]:
        """Return a set of identifiers for the children of the given identifier."""
        # FIXME switch to references
        return nx.ancestors(self.hierarchy, identifier)  # note this is backwards

    def is_descendant(self, descendant: str, ancestor: str) -> bool:
        """Return if the given identifier is a descendent of the ancestor.

        .. code-block:: python

            from pyobo import get_ontology

            obo = get_ontology("go")

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

            from pyobo import get_ontology

            obo = get_ontology("go")

            identifier = "1905571"  # interleukin-10 receptor complex
            is_complex = "0032991" in nx.descendants(obo.hierarchy, identifier)  # should be true
        """
        if self._hierarchy is None:
            self._hierarchy = nx.DiGraph()
            for stanza in self._iter_stanzas(desc=f"[{self.ontology}] getting hierarchy"):
                for parent in stanza.parents:
                    # FIXME add referneces
                    self._hierarchy.add_edge(stanza.identifier, parent.identifier)
        return self._hierarchy

    def to_obonet(self: Obo, *, use_tqdm: bool = False) -> nx.MultiDiGraph:
        """Export as a :mod`obonet` style graph."""
        rv = nx.MultiDiGraph()
        rv.graph.update(
            {
                "name": self.name,
                "ontology": self.ontology,
                "auto-generated-by": self.auto_generated_by,
                "format-version": FORMAT_VERSION,
                "data-version": self.data_version,
                "date": self.date_formatted,
                "typedefs": [typedef.reference.model_dump() for typedef in self.typedefs or []],
                "synonymtypedef": [
                    synonym_typedef.to_obo(ontology_prefix=self.ontology)
                    for synonym_typedef in self.synonym_typedefs or []
                ],
            }
        )

        nodes = {}
        #: a list of 3-tuples u,v,k
        links = []
        typedefs = self._index_typedefs()
        synonym_typedefs = self._index_synonym_typedefs()
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm):
            parents = []
            for parent in stanza.parents:
                if parent is None:
                    raise ValueError("parent should not be none!")
                links.append((stanza.curie, "is_a", parent.curie))
                parents.append(parent.curie)

            relations = []
            for typedef, target in stanza.iterate_relations():
                relations.append(f"{typedef.curie} {target.curie}")
                links.append((stanza.curie, typedef.curie, target.curie))

            for typedef, targets in sorted(stanza.properties.items()):
                for target_or_literal in targets:
                    if isinstance(target_or_literal, curies.Reference):
                        links.append((stanza.curie, typedef.curie, target_or_literal.curie))

            d = {
                "id": stanza.curie,
                "name": stanza.name,
                "def": stanza.definition and stanza._definition_fp(),
                "xref": [xref.curie for xref in stanza.xrefs],
                "is_a": parents,
                "relationship": relations,
                "synonym": [
                    synonym._fp(ontology_prefix=self.ontology, synonym_typedefs=synonym_typedefs)
                    for synonym in stanza.synonyms
                ],
                "property_value": list(
                    stanza._iterate_obo_properties(ontology_prefix=self.ontology, typedefs=typedefs)
                ),
            }
            nodes[stanza.curie] = {k: v for k, v in d.items() if v}

        rv.add_nodes_from(nodes.items())
        for _source, _key, _target in links:
            rv.add_edge(_source, _target, key=_key)

        logger.info(
            "[%s] exported graph with %d nodes",
            self._prefix_version,
            rv.number_of_nodes(),
        )
        return rv

    def get_metadata(self) -> Mapping[str, Any]:
        """Get metadata."""
        return {
            "version": self.data_version,
            "date": self.date and self.date.isoformat(),
        }

    def iterate_references(self, *, use_tqdm: bool = False) -> Iterable[Reference]:
        """Iterate over identifiers."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting identifiers"
        ):
            if self._in_ontology(stanza.reference):
                yield stanza.reference

    def iterate_ids(self, *, use_tqdm: bool = False) -> Iterable[str]:
        """Iterate over identifiers."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting identifiers"
        ):
            if self._in_ontology_strict(stanza.reference):
                yield stanza.identifier

    def get_ids(self, *, use_tqdm: bool = False) -> set[str]:
        """Get the set of identifiers."""
        return set(self.iterate_ids(use_tqdm=use_tqdm))

    def iterate_id_name(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate identifier name pairs."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"
        ):
            if self._in_ontology(stanza.reference) and stanza.name:
                yield stanza.identifier, stanza.name

    def get_id_name_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, str]:
        """Get a mapping from identifiers to names."""
        return dict(self.iterate_id_name(use_tqdm=use_tqdm))

    def iterate_id_definition(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of terms' identifiers and their respective definitions."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting names"
        ):
            if stanza.identifier and stanza.definition:
                yield (
                    stanza.identifier,
                    stanza.definition.strip('"')
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
            stanza.identifier
            for stanza in self._iter_stanzas(
                use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting obsolete"
            )
            if stanza.identifier and stanza.is_obsolete
        }

    ############
    # TYPEDEFS #
    ############

    def iterate_id_species(
        self, *, prefix: str | None = None, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str]]:
        """Iterate over terms' identifiers and respective species (if available)."""
        if prefix is None:
            prefix = NCBITAXON_PREFIX
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting species"
        ):
            if isinstance(stanza, Term) and (species := stanza.get_species(prefix=prefix)):
                yield stanza.identifier, species.identifier

    def get_id_species_mapping(
        self, *, prefix: str | None = None, use_tqdm: bool = False
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

    def iterate_properties(self, *, use_tqdm: bool = False) -> Iterable[tuple[Stanza, Annotation]]:
        """Iterate over tuples of terms, properties, and their values."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting properties"
        ):
            for property_tuple in stanza.get_property_annotations():
                yield stanza, property_tuple

    @property
    def properties_header(self):
        """Property dataframe header."""
        return [f"{self.ontology}_id", "property", "value", "datatype", "language"]

    @property
    def object_properties_header(self):
        """Property dataframe header."""
        return ["source", "predicate", "target"]

    @property
    def literal_properties_header(self):
        """Property dataframe header."""
        return ["source", "predicate", "target", "datatype", "language"]

    def _iter_property_rows(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str, str, str, str]]:
        """Iterate property rows."""
        for term, t in self.iterate_properties(use_tqdm=use_tqdm):
            pred = term._reference(t.predicate, ontology_prefix=self.ontology)
            match t.value:
                case OBOLiteral(value, datatype, language):
                    yield (
                        term.identifier,
                        pred,
                        value,
                        get_preferred_curie(datatype),
                        language or "",
                    )
                case Reference() as obj:
                    yield term.identifier, pred, get_preferred_curie(obj), "", ""
                case _:
                    raise TypeError(f"got: {type(t)} - {t}")

    def get_properties_df(self, *, use_tqdm: bool = False, drop_na: bool = True) -> pd.DataFrame:
        """Get all properties as a dataframe."""
        df = pd.DataFrame(
            self._iter_property_rows(use_tqdm=use_tqdm),
            columns=self.properties_header,
        )
        if drop_na:
            df.dropna(inplace=True)
        return df

    def iter_object_properties(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str, str]]:
        """Iterate over object property triples."""
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm):
            for predicate, target in stanza.iterate_object_properties():
                yield stanza.curie, predicate.curie, target.curie

    def get_object_properties_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get all properties as a dataframe."""
        return pd.DataFrame(
            self.iter_object_properties(use_tqdm=use_tqdm), columns=self.object_properties_header
        )

    def iter_literal_properties(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str, str, str, str]]:
        """Iterate over literal properties quads."""
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm):
            for predicate, target in stanza.iterate_literal_properties():
                yield (
                    stanza.curie,
                    predicate.curie,
                    target.value,
                    target.datatype.curie,
                    target.language or "",
                )

    def get_literal_properties_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get all properties as a dataframe."""
        return pd.DataFrame(self.iter_literal_properties(), columns=self.literal_properties_header)

    def iterate_filtered_properties(
        self, prop: ReferenceHint, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Stanza, str]]:
        """Iterate over tuples of terms and the values for the given property."""
        prop = _ensure_ref(prop)
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm):
            for t in stanza.get_property_annotations():
                if t.predicate != prop:
                    continue
                yield stanza, reference_or_literal_to_str(t.value)

    def get_filtered_properties_df(
        self, prop: ReferenceHint, *, use_tqdm: bool = False
    ) -> pd.DataFrame:
        """Get a dataframe of terms' identifiers to the given property's values."""
        return pd.DataFrame(
            list(self.get_filtered_properties_mapping(prop, use_tqdm=use_tqdm).items()),
            columns=[f"{self.ontology}_id", prop],
        )

    def get_filtered_properties_mapping(
        self, prop: ReferenceHint, *, use_tqdm: bool = False
    ) -> Mapping[str, str]:
        """Get a mapping from a term's identifier to the property.

        .. warning:: Assumes there's only one version of the property for each term.
        """
        return {
            term.identifier: value
            for term, value in self.iterate_filtered_properties(prop, use_tqdm=use_tqdm)
        }

    def get_filtered_properties_multimapping(
        self, prop: ReferenceHint, *, use_tqdm: bool = False
    ) -> Mapping[str, list[str]]:
        """Get a mapping from a term's identifier to the property values."""
        return multidict(
            (term.identifier, value)
            for term, value in self.iterate_filtered_properties(prop, use_tqdm=use_tqdm)
        )

    #############
    # RELATIONS #
    #############

    def iterate_edges(
        self, *, use_tqdm: bool = False, include_xrefs: bool = True
    ) -> Iterable[tuple[Stanza, TypeDef, Reference]]:
        """Iterate over triples of terms, relations, and their targets."""
        _warned: set[ReferenceTuple] = set()
        typedefs = self._index_typedefs()
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm, desc=f"[{self.ontology}] edge"):
            for predicate, reference in stanza._iter_edges(include_xrefs=include_xrefs):
                if td := self._get_typedef(stanza, predicate, _warned, typedefs):
                    yield stanza, td, reference

    @property
    def edges_header(self) -> Sequence[str]:
        """Header for the edges dataframe."""
        return [":START_ID", ":TYPE", ":END_ID"]

    def iterate_relations(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Stanza, TypeDef, Reference]]:
        """Iterate over tuples of terms, relations, and their targets.

        This only outputs stuff from the `relationship:` tag, not
        all possible triples. For that, see :func:`iterate_edges`.
        """
        _warned: set[ReferenceTuple] = set()
        typedefs = self._index_typedefs()
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm, desc=f"[{self.ontology}] relation"):
            for predicate, reference in stanza.iterate_relations():
                if td := self._get_typedef(stanza, predicate, _warned, typedefs):
                    yield stanza, td, reference

    def get_edges_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get an edges dataframe."""
        return pd.DataFrame(self.iterate_edge_rows(use_tqdm=use_tqdm), columns=self.edges_header)

    def iterate_edge_rows(self, use_tqdm: bool = False) -> Iterable[tuple[str, str, str]]:
        """Iterate the edge rows."""
        for term, typedef, reference in self.iterate_edges(use_tqdm=use_tqdm):
            yield term.curie, typedef.curie, reference.curie

    def _get_typedef(
        self,
        term: Stanza,
        predicate: Reference,
        _warned: set[ReferenceTuple],
        typedefs: Mapping[ReferenceTuple, TypeDef],
    ) -> TypeDef | None:
        pp = predicate.pair
        if pp in typedefs:
            return typedefs[pp]
        if pp not in _warned:
            _warn_string = f"[{term.curie}] undefined typedef: {pp}"
            if predicate.name:
                _warn_string += f" ({predicate.name})"
            logger.warning(_warn_string)
            _warned.add(pp)
        return None

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
        relation: ReferenceHint,
        *,
        use_tqdm: bool = False,
    ) -> Iterable[tuple[Stanza, Reference]]:
        """Iterate over tuples of terms and ther targets for the given relation."""
        _pair = _ensure_ref(relation, ontology_prefix=self.ontology).pair
        for term, predicate, reference in self.iterate_relations(use_tqdm=use_tqdm):
            if _pair == predicate.pair:
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
        relation: ReferenceHint,
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
        relation: ReferenceHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Iterable[tuple[Stanza, Reference]]:
        """Iterate over relationships between one identifier and another."""
        for term, reference in self.iterate_filtered_relations(
            relation=relation, use_tqdm=use_tqdm
        ):
            if reference.prefix == target_prefix:
                yield term, reference

    def get_relation_mapping(
        self,
        relation: ReferenceHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> Mapping[str, str]:
        """Get a mapping from the term's identifier to the target's identifier.

        .. warning:: Assumes there's only one version of the property for each term.

         Example usage: get homology between HGNC and MGI:

        >>> from pyobo.sources.hgnc import HGNCGetter
        >>> obo = HGNCGetter()
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
        relation: ReferenceHint,
        target_prefix: str,
        *,
        use_tqdm: bool = False,
    ) -> str | None:
        """Get the value for a bijective relation mapping between this resource and a target resource.

        >>> from pyobo.sources.hgnc import HGNCGetter
        >>> obo = HGNCGetter()
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
        relation: ReferenceHint,
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
            (stanza.identifier, reference)
            for stanza in self._iter_stanzas(
                use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting {typedef.curie}"
            )
            for reference in stanza.get_relationships(typedef)
        )

    ############
    # SYNONYMS #
    ############

    def iterate_synonyms(self, *, use_tqdm: bool = False) -> Iterable[tuple[Stanza, Synonym]]:
        """Iterate over pairs of term and synonym object."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting synonyms"
        ):
            for synonym in sorted(stanza.synonyms):
                yield stanza, synonym

    def iterate_synonym_rows(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of identifier and synonym text."""
        for term, synonym in self.iterate_synonyms(use_tqdm=use_tqdm):
            yield term.identifier, synonym.name

    def get_id_synonyms_mapping(self, *, use_tqdm: bool = False) -> Mapping[str, list[str]]:
        """Get a mapping from identifiers to a list of sorted synonym strings."""
        return multidict(self.iterate_synonym_rows(use_tqdm=use_tqdm))

    def get_literal_mappings(self) -> Iterable[ssslm.LiteralMapping]:
        """Get literal mappings in a standard data model."""
        stanzas: Iterable[Stanza] = itt.chain(self, self.typedefs or [])
        yield from itt.chain.from_iterable(
            stanza.get_literal_mappings()
            for stanza in stanzas
            if self._in_ontology(stanza.reference)
        )

    def _in_ontology(self, reference: Reference | Referenced) -> bool:
        return self._in_ontology_strict(reference) or self._in_ontology_aux(reference)

    def _in_ontology_strict(self, reference: Reference | Referenced) -> bool:
        return reference.prefix == self.ontology

    def _in_ontology_aux(self, reference: Reference | Referenced) -> bool:
        return reference.prefix == "obo" and reference.identifier.startswith(self.ontology + "#")

    #########
    # XREFS #
    #########

    def iterate_xrefs(self, *, use_tqdm: bool = False) -> Iterable[tuple[Stanza, Reference]]:
        """Iterate over xrefs."""
        for stanza in self._iter_stanzas(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting xrefs"
        ):
            xrefs = {xref for _, xref in stanza.get_mappings(add_context=False)}
            for xref in sorted(xrefs):
                yield stanza, xref

    def iterate_filtered_xrefs(
        self, prefix: str, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Stanza, Reference]]:
        """Iterate over xrefs to a given prefix."""
        for term, xref in self.iterate_xrefs(use_tqdm=use_tqdm):
            if xref.prefix == prefix:
                yield term, xref

    def iterate_literal_mapping_rows(self) -> Iterable[ssslm.LiteralMappingTuple]:
        """Iterate over literal mapping rows."""
        for synonym in self.get_literal_mappings():
            yield synonym._as_row()

    def get_literal_mappings_df(self) -> pd.DataFrame:
        """Get a literal mappings dataframe."""
        return ssslm.literal_mappings_to_df(self.get_literal_mappings())

    def iterate_mapping_rows(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str, str, str, str, float | None, str | None]]:
        """Iterate over SSSOM rows for mappings."""
        for stanza in self._iter_stanzas(use_tqdm=use_tqdm):
            for predicate, obj_ref, context in stanza.get_mappings(
                include_xrefs=True, add_context=True
            ):
                yield (
                    get_preferred_curie(stanza),
                    stanza.name,
                    get_preferred_curie(obj_ref),
                    get_preferred_curie(predicate),
                    get_preferred_curie(context.justification),
                    context.confidence if context.confidence is not None else None,
                    get_preferred_curie(context.contributor) if context.contributor else None,
                )

    def get_mappings_df(
        self,
        *,
        use_tqdm: bool = False,
        include_subject_labels: bool = False,
        include_mapping_source_column: bool = False,
    ) -> pd.DataFrame:
        """Get a dataframe with SSSOM extracted from the OBO document."""
        df = pd.DataFrame(self.iterate_mapping_rows(use_tqdm=use_tqdm), columns=SSSOM_DF_COLUMNS)
        if not include_subject_labels:
            del df["subject_label"]

        # if no confidences/contributor, remove that column
        for c in ["confidence", "contributor"]:
            if df[c].isna().all():
                del df[c]

        # append on the mapping_source
        # (https://mapping-commons.github.io/sssom/mapping_source/)
        if include_mapping_source_column:
            df["mapping_source"] = self.ontology

        return df

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

    def iterate_alts(self) -> Iterable[tuple[Stanza, Reference]]:
        """Iterate over alternative identifiers."""
        for stanza in self._iter_stanzas():
            if self._in_ontology(stanza):
                for alt in stanza.alt_ids:
                    yield stanza, alt

    def iterate_alt_rows(self) -> Iterable[tuple[str, str]]:
        """Iterate over pairs of terms' primary identifiers and alternate identifiers."""
        for term, alt in self.iterate_alts():
            yield term.identifier, alt.identifier

    def get_id_alts_mapping(self) -> Mapping[str, list[str]]:
        """Get a mapping from identifiers to a list of alternative identifiers."""
        return multidict((term.identifier, alt.identifier) for term, alt in self.iterate_alts())


@dataclass
class TypeDef(Stanza):
    """A type definition in OBO.

    See the subsection of https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.2.2.
    """

    reference: Annotated[Reference, 1]
    is_anonymous: Annotated[bool | None, 2] = None
    # 3 - name is covered by reference
    namespace: Annotated[str | None, 4] = None
    # 5 alt_id is part of proerties
    definition: Annotated[str | None, 6] = None
    comment: Annotated[str | None, 7] = None
    subsets: Annotated[list[Reference], 8] = field(default_factory=list)
    synonyms: Annotated[list[Synonym], 9] = field(default_factory=list)
    xrefs: Annotated[list[Reference], 10] = field(default_factory=list)
    _axioms: AnnotationsDict = field(default_factory=lambda: defaultdict(list))
    properties: Annotated[PropertiesHint, 11] = field(default_factory=lambda: defaultdict(list))
    domain: Annotated[Reference | None, 12, "typedef-only"] = None
    range: Annotated[Reference | None, 13, "typedef-only"] = None
    builtin: Annotated[bool | None, 14] = None
    holds_over_chain: Annotated[list[list[Reference]], 15, "typedef-only"] = field(
        default_factory=list
    )
    is_anti_symmetric: Annotated[bool | None, 16, "typedef-only"] = None
    is_cyclic: Annotated[bool | None, 17, "typedef-only"] = None
    is_reflexive: Annotated[bool | None, 18, "typedef-only"] = None
    is_symmetric: Annotated[bool | None, 19, "typedef-only"] = None
    is_transitive: Annotated[bool | None, 20, "typedef-only"] = None
    is_functional: Annotated[bool | None, 21, "typedef-only"] = None
    is_inverse_functional: Annotated[bool | None, 22, "typedef-only"] = None
    parents: Annotated[list[Reference], 23] = field(default_factory=list)
    intersection_of: Annotated[IntersectionOfHint, 24] = field(default_factory=list)
    union_of: Annotated[list[Reference], 25] = field(default_factory=list)
    equivalent_to: Annotated[list[Reference], 26] = field(default_factory=list)
    disjoint_from: Annotated[list[Reference], 27] = field(default_factory=list)
    # TODO inverse should be inverse_of, cardinality any
    inverse: Annotated[Reference | None, 28, "typedef-only"] = None
    # TODO check if there are any examples of this being multiple
    transitive_over: Annotated[list[Reference], 29, "typedef-only"] = field(default_factory=list)
    equivalent_to_chain: Annotated[list[list[Reference]], 30, "typedef-only"] = field(
        default_factory=list
    )
    #: From the OBO spec:
    #:
    #:   For example: spatially_disconnected_from is disjoint_over part_of, in that two
    #:   disconnected entities have no parts in common. This can be translated to OWL as:
    #:   ``disjoint_over(R S), R(A B) ==> (S some A) disjointFrom (S some B)``
    disjoint_over: Annotated[list[Reference], 31] = field(default_factory=list)
    relationships: Annotated[RelationsHint, 32] = field(default_factory=lambda: defaultdict(list))
    is_obsolete: Annotated[bool | None, 33] = None
    created_by: Annotated[str | None, 34] = None
    creation_date: Annotated[datetime.datetime | None, 35] = None
    # TODO expand_assertion_to
    # TODO expand_expression_to
    #: Whether this relationship is a metadata tag. Properties that are marked as metadata tags are
    #: used to record object metadata. Object metadata is additional information about an object
    #: that is useful to track, but does not impact the definition of the object or how it should
    #: be treated by a reasoner. Metadata tags might be used to record special term synonyms or
    #: structured notes about a term, for example.
    is_metadata_tag: Annotated[bool | None, 40, "typedef-only"] = None
    is_class_level: Annotated[bool | None, 41] = None

    type: StanzaType = "TypeDef"

    def __hash__(self) -> int:
        # have to re-define hash because of the @dataclass
        return hash((self.__class__, self.prefix, self.identifier))

    def _get_references(self) -> dict[str, set[Reference]]:
        rv = super()._get_references()

        def _add(r: Reference) -> None:
            rv[r.prefix].add(r)

        if self.domain:
            _add(self.domain)
        if self.range:
            _add(self.range)
        if self.inverse:
            _add(self.inverse)

        # TODO all of the properties, which are from oboInOwl
        for rr in itt.chain(self.transitive_over, self.disjoint_over):
            _add(rr)
        for part in itt.chain(self.holds_over_chain, self.equivalent_to_chain):
            for rr in part:
                _add(rr)
        return dict(rv)

    def iterate_obo_lines(
        self,
        ontology_prefix: str,
        synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] | None = None,
        typedefs: Mapping[ReferenceTuple, TypeDef] | None = None,
    ) -> Iterable[str]:
        """Iterate over the lines to write in an OBO file.

        :param ontology_prefix:
            The prefix of the ontology into which the type definition is being written.
            This is used for compressing builtin identifiers
        :yield:
            The lines to write to an OBO file

        `S.3.5.5 <https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.3.5.5>`_
        of the OBO Flat File Specification v1.4 says tags should appear in the following order:

        1. id
        2. is_anonymous
        3. name
        4. namespace
        5. alt_id
        6. def
        7. comment
        8. subset
        9. synonym
        10. xref
        11. property_value
        12. domain
        13. range
        14. builtin
        15. holds_over_chain
        16. is_anti_symmetric
        17. is_cyclic
        18. is_reflexive
        19. is_symmetric
        20. is_transitive
        21. is_functional
        22. is_inverse_functional
        23. is_a
        24. intersection_of
        25. union_of
        26. equivalent_to
        27. disjoint_from
        28. inverse_of
        29. transitive_over
        30. equivalent_to_chain
        31. disjoint_over
        32. relationship
        33. is_obsolete
        34. created_by
        35. creation_date
        36. replaced_by
        37. consider
        38. expand_assertion_to
        39. expand_expression_to
        40. is_metadata_tag
        41. is_class_level
        """
        if synonym_typedefs is None:
            synonym_typedefs = {}
        if typedefs is None:
            typedefs = {}

        yield "\n[Typedef]"
        # 1
        yield f"id: {reference_escape(self.reference, ontology_prefix=ontology_prefix)}"
        # 2
        yield from _boolean_tag("is_anonymous", self.is_anonymous)
        # 3
        if self.name:
            yield f"name: {self.name}"
        # 4
        if self.namespace:
            yield f"namespace: {self.namespace}"
        # 5
        yield from _reference_list_tag("alt_id", self.alt_ids, ontology_prefix)
        # 6
        if self.definition:
            yield f"def: {self._definition_fp()}"
        # 7
        if self.comment:
            yield f"comment: {self.comment}"
        # 8
        yield from _reference_list_tag("subset", self.subsets, ontology_prefix)
        # 9
        for synonym in self.synonyms:
            yield synonym.to_obo(ontology_prefix=ontology_prefix, synonym_typedefs=synonym_typedefs)
        # 10
        yield from self._iterate_xref_obo(ontology_prefix=ontology_prefix)
        # 11
        yield from self._iterate_obo_properties(
            ontology_prefix=ontology_prefix,
            skip_predicate_objects=v.SKIP_PROPERTY_PREDICATES_OBJECTS,
            skip_predicate_literals=v.SKIP_PROPERTY_PREDICATES_LITERAL,
            typedefs=typedefs,
        )
        # 12
        if self.domain:
            yield f"domain: {reference_escape(self.domain, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 13
        if self.range:
            yield f"range: {reference_escape(self.range, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 14
        yield from _boolean_tag("builtin", self.builtin)
        # 15
        yield from _chain_tag("holds_over_chain", self.holds_over_chain, ontology_prefix)
        # 16
        yield from _boolean_tag("is_anti_symmetric", self.is_anti_symmetric)
        # 17
        yield from _boolean_tag("is_cyclic", self.is_cyclic)
        # 18
        yield from _boolean_tag("is_reflexive", self.is_reflexive)
        # 19
        yield from _boolean_tag("is_symmetric", self.is_symmetric)
        # 20
        yield from _boolean_tag("is_transitive", self.is_transitive)
        # 21
        yield from _boolean_tag("is_functional", self.is_functional)
        # 22
        yield from _boolean_tag("is_inverse_functional", self.is_inverse_functional)
        # 23
        yield from _reference_list_tag("is_a", self.parents, ontology_prefix)
        # 24
        yield from self._iterate_intersection_of_obo(ontology_prefix=ontology_prefix)
        # 25
        yield from _reference_list_tag("union_of", self.union_of, ontology_prefix)
        # 26
        yield from _reference_list_tag("equivalent_to", self.equivalent_to, ontology_prefix)
        # 27
        yield from _reference_list_tag("disjoint_from", self.disjoint_from, ontology_prefix)
        # 28
        if self.inverse:
            yield f"inverse_of: {reference_escape(self.inverse, ontology_prefix=ontology_prefix, add_name_comment=True)}"
        # 29
        yield from _reference_list_tag("transitive_over", self.transitive_over, ontology_prefix)
        # 30
        yield from _chain_tag("equivalent_to_chain", self.equivalent_to_chain, ontology_prefix)
        # 31 disjoint_over, see https://github.com/search?q=%22disjoint_over%3A%22+path%3A*.obo&type=code
        yield from _reference_list_tag(
            "disjoint_over", self.disjoint_over, ontology_prefix=ontology_prefix
        )
        # 32
        yield from self._iterate_obo_relations(ontology_prefix=ontology_prefix, typedefs=typedefs)
        # 33
        yield from _boolean_tag("is_obsolete", self.is_obsolete)
        # 34
        if self.created_by:
            yield f"created_by: {self.created_by}"
        # 35
        if self.creation_date is not None:
            yield f"creation_date: {self.creation_date.isoformat()}"
        # 36
        yield from _tag_property_targets(
            "replaced_by", self, v.term_replaced_by, ontology_prefix=ontology_prefix
        )
        # 37
        yield from _tag_property_targets(
            "consider", self, v.see_also, ontology_prefix=ontology_prefix
        )
        # 38 TODO expand_assertion_to
        # 39 TODO expand_expression_to
        # 40
        yield from _boolean_tag("is_metadata_tag", self.is_metadata_tag)
        # 41
        yield from _boolean_tag("is_class_level", self.is_class_level)

    @classmethod
    def from_triple(cls, prefix: str, identifier: str, name: str | None = None) -> TypeDef:
        """Create a typedef from a reference."""
        return cls(reference=Reference(prefix=prefix, identifier=identifier, name=name))

    @classmethod
    def default(
        cls, prefix: str, identifier: str, *, name: str | None = None, is_metadata_tag: bool
    ) -> Self:
        """Construct a default type definition from within the OBO namespace."""
        return cls(
            reference=default_reference(prefix, identifier, name=name),
            is_metadata_tag=is_metadata_tag,
        )


class AdHocOntologyBase(Obo):
    """A base class for ad-hoc ontologies."""


def make_ad_hoc_ontology(
    _ontology: str,
    _name: str | None = None,
    _auto_generated_by: str | None = None,
    _typedefs: list[TypeDef] | None = None,
    _synonym_typedefs: list[SynonymTypeDef] | None = None,
    _date: datetime.datetime | None = None,
    _data_version: str | None = None,
    _idspaces: Mapping[str, str] | None = None,
    _root_terms: list[Reference] | None = None,
    _subsetdefs: list[tuple[Reference, str]] | None = None,
    _property_values: list[Annotation] | None = None,
    _imports: list[str] | None = None,
    *,
    terms: list[Term] | None = None,
) -> Obo:
    """Make an ad-hoc ontology."""

    class AdHocOntology(AdHocOntologyBase):
        """An ad hoc ontology created from an OBO file."""

        ontology = _ontology
        name = _name
        auto_generated_by = _auto_generated_by
        typedefs = _typedefs
        synonym_typedefs = _synonym_typedefs
        idspaces = _idspaces
        root_terms = _root_terms
        subsetdefs = _subsetdefs
        property_values = _property_values
        imports = _imports

        def __post_init__(self):
            self.date = _date
            self.data_version = _data_version

        def iter_terms(self, force: bool = False) -> Iterable[Term]:
            """Iterate over terms in the ad hoc ontology."""
            return terms or []

    return AdHocOntology()


HUMAN_TERM = Term(reference=v.HUMAN)
CHARLIE_TERM = Term(reference=v.CHARLIE, type="Instance").append_parent(HUMAN_TERM)
PYOBO_INJECTED = "Injected by PyOBO"
