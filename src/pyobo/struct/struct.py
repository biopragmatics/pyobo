"""Data structures for OBO."""

from __future__ import annotations

import datetime
import gzip
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
from typing import Annotated, Any, ClassVar, Literal, TextIO

import bioregistry
import click
import curies
import networkx as nx
import pandas as pd
from curies import ReferenceTuple
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
)
from .struct_utils import (
    Annotation,
    AxiomsHint,
    IntersectionOfHint,
    PropertiesHint,
    ReferenceHint,
    RelationsHint,
    Stanza,
    UnionOfHint,
    _chain_tag,
    _ensure_ref,
    _tag_property_targets,
)
from .utils import _boolean_tag, obo_escape_slim
from ..api.utils import get_version
from ..constants import (
    BUILD_SUBDIRECTORY_NAME,
    CACHE_SUBDIRECTORY_NAME,
    DATE_FORMAT,
    NCBITAXON_PREFIX,
    RELATION_ID,
    RELATION_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)
from ..utils.io import multidict, write_iterable_tsv
from ..utils.path import prefix_directory_join
from ..version import get_version as get_pyobo_version

__all__ = [
    "Obo",
    "Synonym",
    "SynonymTypeDef",
    "Term",
    "abbreviation",
    "acronym",
    "int_identifier_sort_key",
    "make_ad_hoc_ontology",
]

logger = logging.getLogger(__name__)

DEFAULT_SPECIFICITY: _cv.SynonymScope = "EXACT"

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
UNSPECIFIED_MATCHING_CURIE = "sempav:UnspecifiedMatching"
FORMAT_VERSION = "1.4"


@dataclass
class Synonym:
    """A synonym with optional specificity and references."""

    #: The string representing the synonym
    name: str

    #: The specificity of the synonym
    specificity: _cv.SynonymScope | None = None

    #: The type of synonym. Must be defined in OBO document!
    type: Reference | None = None

    #: References to articles where the synonym appears
    provenance: list[Reference] = field(default_factory=list)

    #: Extra annotations
    annotations: list[tuple[Reference, Reference]] = field(default_factory=list)

    def __lt__(self, other: Synonym) -> bool:
        """Sort lexically by name."""
        return self._sort_key() < other._sort_key()

    def _sort_key(self) -> tuple[str, _cv.SynonymScope, str]:
        return (
            self.name,
            self.specificity or DEFAULT_SPECIFICITY,
            self.type.curie if self.type else "",
        )

    @property
    def predicate(self) -> curies.NamedReference:
        """Get the specificity reference."""
        return _cv.synonym_scopes[self.specificity or DEFAULT_SPECIFICITY]

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
        std = _synonym_typedef_warn(ontology_prefix, self.type, synonym_typedefs)
        if std is not None and std.specificity is not None:
            specificity = std.specificity
        elif self.specificity:
            specificity = self.specificity
        else:
            specificity = DEFAULT_SPECIFICITY
        x = f'"{self._escape(self.name)}" {specificity}'
        if self.type is not None:
            x = f"{x} {reference_escape(self.type, ontology_prefix=ontology_prefix)}"
        return f"{x} [{comma_separate_references(self.provenance)}]"

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace('"', '\\"')


@dataclass
class SynonymTypeDef(Referenced):
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
class Term(Referenced, Stanza):
    """A term in OBO."""

    #: The primary reference for the entity
    reference: Reference

    #: A description of the entity
    definition: str | None = None

    #: Object properties
    relationships: RelationsHint = field(default_factory=lambda: defaultdict(list))

    _axioms: AxiomsHint = field(default_factory=lambda: defaultdict(list))

    properties: PropertiesHint = field(default_factory=lambda: defaultdict(list))

    #: Relationships with the default "is_a"
    parents: list[Reference] = field(default_factory=list)

    # TODO add intersection and union to relation output
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

    type: Literal["Term", "Instance"] = "Term"

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
    def auto(
        cls,
        prefix: str,
        identifier: str,
    ) -> Term:
        """Create a term from a reference."""
        from ..api import get_definition

        return cls(
            reference=Reference.auto(prefix=prefix, identifier=identifier),
            definition=get_definition(prefix, identifier),
        )

    def append_see_also_url(self, url: str) -> Self:
        """Add a see also property."""
        return self.annotate_literal(
            v.see_also, url, datatype=Reference(prefix="xsd", identifier="anyURI")
        )

    def extend_parents(self, references: Collection[Reference]) -> None:
        """Add a collection of parents to this entity."""
        warnings.warn("use append_parent", DeprecationWarning, stacklevel=2)
        if any(x is None for x in references):
            raise ValueError("can not append a collection of parents containing a null parent")
        self.parents.extend(references)

    def get_property_literals(self, prop: ReferenceHint) -> list[str]:
        """Get properties from the given key."""
        rv = []
        for t in self.properties.get(_ensure_ref(prop), []):
            match t:
                case Reference():
                    rv.append(get_preferred_curie(t))
                case OBOLiteral(value, _):
                    rv.append(value)
        return rv

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
        axioms = self._prepare_mapping_axioms(
            mapping_justification=mapping_justification,
            confidence=confidence,
            contributor=contributor,
        )
        self.annotate_object(v.exact_match, reference, axioms=axioms)
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
        if self.definition or self.provenance:
            yield f"def: {self._definition_fp()}"
        # 7
        for x in self.get_property_values(v.comment):
            if isinstance(x, OBOLiteral):
                yield f'comment: "{x.value}"'
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
                skip_predicates=[
                    v.term_replaced_by,
                    v.see_also,
                    v.alternative_term,
                ],
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
        # 20 TODO creation_date
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

    @staticmethod
    def _reference(
        predicate: Reference, ontology_prefix: str, add_name_comment: bool = False
    ) -> str:
        return reference_escape(
            predicate, ontology_prefix=ontology_prefix, add_name_comment=add_name_comment
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


def int_identifier_sort_key(obo: Obo, term: Term) -> int:
    """Sort terms by integer identifiers."""
    return int(term.identifier)


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

    term_sort_key: ClassVar[Callable[[Obo, Term], int] | None] = None

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

        if self.idspaces is None:
            self.idspaces = {}
        self.idspaces.update(
            dcterms="http://purl.org/dc/terms/",
            skos="http://www.w3.org/2004/02/skos/core#",
        )

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
    def cli(cls, *, default_rewrite: bool = False) -> Any:
        """Run the CLI for this class."""
        cli = cls.get_cls_cli(default_rewrite=default_rewrite)
        return cli()

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
        @click.option(
            "--version", help="Specify data version to get. Use this if bioversions is acting up."
        )
        def _main(force: bool, owl: bool, version: str | None, rewrite: bool):
            rewrite = True
            try:
                inst = cls(force=force, data_version=version)
            except Exception as e:
                click.secho(f"[{cls.ontology}] Got an exception during instantiation - {type(e)}")
                sys.exit(1)
            inst.write_default(
                write_obograph=True,
                write_obo=True,
                write_owl=owl,
                write_nodes=True,
                write_edges=True,
                force=force or rewrite,
                use_tqdm=True,
            )

        return _main

    @property
    def date_formatted(self) -> str:
        """Get the date as a formatted string."""
        return (self.date if self.date else datetime.datetime.now()).strftime(DATE_FORMAT)

    def _iter_terms(self, use_tqdm: bool = False, desc: str = "terms") -> Iterable[Term]:
        if use_tqdm:
            total: int | None
            try:
                total = len(self._items_accessor)
            except TypeError:
                total = None
            yield from tqdm(self, desc=desc, unit_scale=True, unit="term", total=total)
        else:
            yield from self

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
        for prefix, url in sorted((self.idspaces or {}).items()):
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
        for term in self:
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

    def _iterate_property_pairs(self) -> Iterable[tuple[Reference, Reference | OBOLiteral]]:
        # Title
        if self.name:
            yield (
                v.has_title,
                OBOLiteral(self.name, Reference(prefix="xsd", identifier="string")),
            )

        # License
        # TODO add SPDX to idspaces and use as a CURIE?
        if license_spdx_id := bioregistry.get_license(self.ontology):
            yield (
                v.has_license,
                OBOLiteral(license_spdx_id, Reference(prefix="xsd", identifier="string")),
            )

        # Description
        if description := bioregistry.get_description(self.ontology):
            description = obo_escape_slim(description.strip())
            yield (
                v.has_description,
                OBOLiteral(description.strip(), Reference(prefix="xsd", identifier="string")),
            )

        # Root terms
        for root_term in self.root_terms or []:
            yield v.has_ontology_root_term, root_term

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
            it = tqdm(it, desc=f"Writing {self.ontology}", unit_scale=True, unit="line")
        if isinstance(file, str | Path | os.PathLike):
            with open(file, "w") as fh:
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
        with gzip.open(path, "wt") as file:
            json.dump(nx.node_link_data(graph), file)

    def _path(self, *parts: str, name: str | None = None) -> Path:
        return prefix_directory_join(self.ontology, *parts, name=name, version=self.data_version)

    def _cache(self, *parts: str, name: str | None = None) -> Path:
        return self._path(CACHE_SUBDIRECTORY_NAME, *parts, name=name)

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
        warnings.warn("use _mappings_path", DeprecationWarning, stacklevel=2)
        return self._cache(name="xrefs.tsv")

    @property
    def _mappings_path(self) -> Path:
        return self._cache(name="mappings.tsv")

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
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.obo")

    @property
    def _obograph_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.json")

    @property
    def _owl_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.owl")

    @property
    def _obonet_gz_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.obonet.json.gz")

    @property
    def _nodes_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.nodes.tsv")

    @property
    def _edges_path(self) -> Path:
        return self._path(BUILD_SUBDIRECTORY_NAME, name=f"{self.ontology}.edges.tsv")

    def write_default(
        self,
        use_tqdm: bool = False,
        force: bool = False,
        write_obo: bool = False,
        write_obonet: bool = False,
        write_obograph: bool = False,
        write_owl: bool = False,
        write_nodes: bool = True,
        write_edges: bool = True,
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
            ("mappings", self._mappings_path, SSSOM_DF_COLUMNS, self.iterate_mapping_rows),
            ("relations", self._relations_path, self.relations_header, self.iter_relation_rows),
            ("edges", self._edges_path, self.edges_header, self.iterate_edge_rows),
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

        typedefs = self._index_typedefs()
        for relation in (v.is_a, v.has_part, v.part_of, v.from_species, v.orthologous):
            if relation is not v.is_a and relation.pair not in typedefs:
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
            tqdm.write(f"[{self.ontology}] writing to {self._obo_path}")
            self.write_obo(self._obo_path, use_tqdm=use_tqdm)
        if write_obograph and (not self._obograph_path.exists() or force):
            self.write_obograph(self._obograph_path)
        if write_owl and (not self._owl_path.exists() or force):
            import bioontologies.robot

            bioontologies.robot.convert(self._obo_path, self._owl_path)
        if write_obonet and (not self._obonet_gz_path.exists() or force):
            logger.debug("writing obonet to %s", self._obonet_gz_path)
            self.write_obonet_gz(self._obonet_gz_path)
        if write_nodes:
            self.get_graph().get_nodes_df().to_csv(self._nodes_path, sep="\t", index=False)

    @property
    def _items_accessor(self):
        if self._items is None:
            # if the term sort key is None, then the terms get sorted by their reference
            self._items = sorted(self.iter_terms(force=self.force), key=self.term_sort_key)
        return self._items

    def __iter__(self) -> Iterator[Term]:
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
            for term in self._iter_terms(desc=f"[{self.ontology}] getting hierarchy"):
                for parent in term.parents:
                    self._hierarchy.add_edge(term.identifier, parent.identifier)
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
        for term in self._iter_terms(use_tqdm=use_tqdm):
            parents = []
            for parent in term.parents:
                if parent is None:
                    raise ValueError("parent should not be none!")
                links.append((term.curie, "is_a", parent.curie))
                parents.append(parent.curie)

            relations = []
            for typedef, target in term.iterate_relations():
                relations.append(f"{typedef.curie} {target.curie}")
                links.append((term.curie, typedef.curie, target.curie))

            for typedef, targets in sorted(term.properties.items()):
                for target_or_literal in targets:
                    if isinstance(target_or_literal, curies.Reference):
                        links.append((term.curie, typedef.curie, target_or_literal.curie))

            d = {
                "id": term.curie,
                "name": term.name,
                "def": (term.definition or term.provenance) and term._definition_fp(),
                "xref": [xref.curie for xref in term.xrefs],
                "is_a": parents,
                "relationship": relations,
                "synonym": [
                    synonym._fp(ontology_prefix=self.ontology, synonym_typedefs=synonym_typedefs)
                    for synonym in term.synonyms
                ],
                "property_value": list(
                    term._iterate_obo_properties(ontology_prefix=self.ontology, typedefs=typedefs)
                ),
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
        self, *, prefix: str | None = None, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str]]:
        """Iterate over terms' identifiers and respective species (if available)."""
        if prefix is None:
            prefix = NCBITAXON_PREFIX
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting species"):
            species = term.get_species(prefix=prefix)
            if species:
                yield term.identifier, species.identifier

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

    def iterate_properties(self, *, use_tqdm: bool = False) -> Iterable[tuple[Term, Annotation]]:
        """Iterate over tuples of terms, properties, and their values."""
        for term in self._iter_terms(
            use_tqdm=use_tqdm, desc=f"[{self.ontology}] getting properties"
        ):
            for property_tuple in term.get_property_annotations():
                yield term, property_tuple

    @property
    def properties_header(self):
        """Property dataframe header."""
        return [f"{self.ontology}_id", "property", "value", "datatype"]

    def iter_property_rows(self, *, use_tqdm: bool = False) -> Iterable[tuple[str, str, str, str]]:
        """Iterate property rows."""
        tuple[Term, Reference, Reference, None] | tuple[Term, Reference, str, Reference]
        for term, t in self.iterate_properties(use_tqdm=use_tqdm):
            pred = term._reference(t.predicate, ontology_prefix=self.ontology)
            match t.value:
                case OBOLiteral(value, datatype):
                    yield (term.identifier, pred, value, get_preferred_curie(datatype))
                case Reference() as obj:
                    yield (term.identifier, pred, get_preferred_curie(obj), "")
                case _:
                    raise TypeError(f"got: {type(t)} - {t}")

    def get_properties_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get all properties as a dataframe."""
        return pd.DataFrame(
            list(self.iter_property_rows(use_tqdm=use_tqdm)),
            columns=self.properties_header,
        )

    def iterate_filtered_properties(
        self, prop: ReferenceHint, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Term, str]]:
        """Iterate over tuples of terms and the values for the given property."""
        prop = _ensure_ref(prop)
        for term in self._iter_terms(use_tqdm=use_tqdm):
            for t in term.get_property_annotations():
                if t.predicate != prop:
                    continue
                match t.value:
                    case OBOLiteral(value, _datatype):
                        yield term, value
                    case Reference():
                        yield term, get_preferred_curie(t.value)

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

    def iterate_edges(self, *, use_tqdm: bool = False) -> Iterable[tuple[Term, TypeDef, Reference]]:
        """Iterate over triples of terms, relations, and their targets."""
        _warned: set[ReferenceTuple] = set()
        typedefs = self._index_typedefs()
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] edge"):
            for predicate, reference in term._iter_edges():
                if td := self._get_typedef(term, predicate, _warned, typedefs):
                    yield term, td, reference

    @property
    def edges_header(self) -> Sequence[str]:
        """Header for the edges dataframe."""
        return [":START_ID", ":TYPE", ":END_ID"]

    def iterate_relations(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[Term, TypeDef, Reference]]:
        """Iterate over tuples of terms, relations, and their targets.

        This only outputs stuff from the `relationship:` tag, not
        all possible triples. For that, see :func:`iterate_edges`.
        """
        _warned: set[ReferenceTuple] = set()
        typedefs = self._index_typedefs()
        for term in self._iter_terms(use_tqdm=use_tqdm, desc=f"[{self.ontology}] relation"):
            for predicate, reference in term.iterate_relations():
                if td := self._get_typedef(term, predicate, _warned, typedefs):
                    yield term, td, reference

    def iterate_edge_rows(self, use_tqdm: bool = False) -> Iterable[tuple[str, str, str]]:
        """Iterate the edge rows."""
        for term, typedef, reference in self.iterate_edges(use_tqdm=use_tqdm):
            yield (term.curie, typedef.curie, reference.curie)

    def _get_typedef(
        self,
        term: Term,
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
    ) -> Iterable[tuple[Term, Reference]]:
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
    ) -> Iterable[tuple[Term, Reference]]:
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
            for synonym in sorted(term.synonyms):
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

    def iterate_mapping_rows(
        self, *, use_tqdm: bool = False
    ) -> Iterable[tuple[str, str, str, str, str, float | None, str | None]]:
        """Iterate over SSSOM rows for mappings."""
        for term in self._iter_terms(use_tqdm=use_tqdm):
            for predicate, obj_ref, context in term.get_mappings(
                include_xrefs=True, add_context=True
            ):
                yield (
                    get_preferred_curie(term),
                    term.name,
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

    @property
    def xrefs_header(self):
        """The header for the xref dataframe."""
        warnings.warn("use SSSOM_DF_COLUMNS instead", DeprecationWarning, stacklevel=2)
        return [f"{self.ontology}_id", TARGET_PREFIX, TARGET_ID]

    def get_xrefs_df(self, *, use_tqdm: bool = False) -> pd.DataFrame:
        """Get a dataframe of all xrefs extracted from the OBO document."""
        warnings.warn("use ontology.get_mappings_df instead", DeprecationWarning, stacklevel=2)

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


@dataclass
class TypeDef(Referenced, Stanza):
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
    _axioms: AxiomsHint = field(default_factory=lambda: defaultdict(list))
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

    def __hash__(self) -> int:
        # have to re-define hash because of the @dataclass
        return hash((self.__class__, self.prefix, self.identifier))

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
            skip_predicates={
                v.term_replaced_by,
                v.see_also,
                v.alternative_term,
            },
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
    def default(cls, prefix: str, identifier: str, *, name: str | None = None) -> Self:
        """Construct a default type definition from within the OBO namespace."""
        return cls(reference=default_reference(prefix, identifier, name=name))


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

    class AdHocOntology(Obo):
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
