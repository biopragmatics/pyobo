"""OBO Readers."""

from __future__ import annotations

import logging
import typing as t
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from io import StringIO
from pathlib import Path
from textwrap import dedent
from typing import Any

import bioregistry
import networkx as nx
from curies import ReferenceTuple
from curies.preprocessing import BlocklistError
from curies.vocabulary import SynonymScope
from more_itertools import pairwise
from tqdm.auto import tqdm

from .reader_utils import (
    _chomp_axioms,
    _chomp_references,
    _chomp_specificity,
    _chomp_typedef,
    _parse_provenance_list,
)
from .. import vocabulary as v
from ..reference import OBOLiteral, _obo_parse_identifier
from ..struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    TypeDef,
    default_reference,
    make_ad_hoc_ontology,
)
from ..struct_utils import Annotation, Stanza
from ..typedef import comment as has_comment
from ..typedef import default_typedefs, has_ontology_root_term
from ...constants import DATE_FORMAT, PROVENANCE_PREFIXES
from ...identifier_utils import (
    NotCURIEError,
    ParseError,
    UnparsableIRIError,
    _is_valid_identifier,
    _parse_str_or_curie_or_uri_helper,
    get_rules,
)
from ...utils.cache import write_gzipped_graph
from ...utils.io import safe_open
from ...utils.misc import STATIC_VERSION_REWRITES, cleanup_version

__all__ = [
    "from_obo_path",
    "from_obonet",
    "from_str",
]

logger = logging.getLogger(__name__)


def from_obo_path(
    path: str | Path,
    prefix: str | None = None,
    *,
    strict: bool = False,
    version: str | None,
    upgrade: bool = True,
    use_tqdm: bool = False,
    ignore_obsolete: bool = False,
    _cache_path: Path | None = None,
) -> Obo:
    """Get the OBO graph from a path."""
    path = Path(path).expanduser().resolve()
    if path.suffix.endswith(".zip"):
        import io
        import zipfile

        logger.info("[%s] parsing zipped OBO with obonet from %s", prefix or "<unknown>", path)
        with zipfile.ZipFile(path) as zf:
            with zf.open(path.name.removesuffix(".zip"), "r") as file:
                content = file.read().decode("utf-8")
                graph = _read_obo(
                    io.StringIO(content), prefix, ignore_obsolete=ignore_obsolete, use_tqdm=use_tqdm
                )
    else:
        logger.info("[%s] parsing OBO with obonet from %s", prefix or "<unknown>", path)
        with safe_open(path, read=True) as file:
            graph = _read_obo(file, prefix, ignore_obsolete=ignore_obsolete, use_tqdm=use_tqdm)

    if prefix:
        # Make sure the graph is named properly
        _clean_graph_ontology(graph, prefix)

    if _cache_path:
        logger.info("[%s] writing obonet cache to %s", prefix, _cache_path)
        write_gzipped_graph(path=_cache_path, graph=graph)

    # Convert to an Obo instance and return
    return from_obonet(graph, strict=strict, version=version, upgrade=upgrade, use_tqdm=use_tqdm)


def _read_obo(
    filelike, prefix: str | None, ignore_obsolete: bool, use_tqdm: bool = True
) -> nx.MultiDiGraph:
    import obonet

    return obonet.read_obo(
        tqdm(
            filelike,
            unit_scale=True,
            desc=f"[{prefix or ''}] parsing OBO",
            disable=not use_tqdm,
            leave=True,
        ),
        ignore_obsolete=ignore_obsolete,
    )


def _normalize_prefix_strict(prefix: str) -> str:
    n = bioregistry.normalize_prefix(prefix)
    if n is None:
        raise ValueError(f"unknown prefix: {prefix}")
    return n


def from_str(
    text: str,
    *,
    strict: bool = False,
    version: str | None = None,
    upgrade: bool = True,
    ignore_obsolete: bool = False,
    use_tqdm: bool = False,
) -> Obo:
    """Read an ontology from a string representation."""
    import obonet

    text = dedent(text).strip()
    io = StringIO()
    io.write(text)
    io.seek(0)
    graph = obonet.read_obo(io, ignore_obsolete=ignore_obsolete)
    return from_obonet(graph, strict=strict, version=version, upgrade=upgrade, use_tqdm=use_tqdm)


def from_obonet(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = False,
    version: str | None = None,
    upgrade: bool = True,
    use_tqdm: bool = False,
) -> Obo:
    """Get all of the terms from a OBO graph."""
    ontology_prefix_raw = graph.graph["ontology"]
    ontology_prefix = _normalize_prefix_strict(ontology_prefix_raw)
    logger.info("[%s] extracting OBO using obonet", ontology_prefix)

    date = _get_date(graph=graph, ontology_prefix=ontology_prefix)
    name = _get_name(graph=graph, ontology_prefix=ontology_prefix)
    imports = graph.graph.get("import")

    macro_config = MacroConfig(graph.graph, strict=strict, ontology_prefix=ontology_prefix)

    data_version = _clean_graph_version(
        graph, ontology_prefix=ontology_prefix, version=version, date=date
    )
    if data_version and "/" in data_version:
        raise ValueError(
            f"[{ontology_prefix}] slashes not allowed in data versions because of filesystem usage: {data_version}"
        )

    missing_typedefs: set[ReferenceTuple] = set()

    subset_typedefs = _get_subsetdefs(graph.graph, ontology_prefix=ontology_prefix)

    root_terms: list[Reference] = []
    property_values: list[Annotation] = []
    for ann in iterate_node_properties(
        graph.graph,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        node=Reference(prefix="obo", identifier=ontology_prefix),
        strict=strict,
        context="graph property",
    ):
        if ann.predicate.pair == has_ontology_root_term.pair:
            match ann.value:
                case OBOLiteral():
                    logger.warning(
                        "[%s] tried to use a literal as an ontology root: %s",
                        ontology_prefix,
                        ann.value.value,
                    )
                    continue
                case Reference():
                    root_terms.append(ann.value)
        else:
            property_values.append(ann)

    for remark in graph.graph.get("remark", []):
        property_values.append(Annotation(has_comment.reference, OBOLiteral.string(remark)))

    idspaces: dict[str, str] = {}
    for x in graph.graph.get("idspace", []):
        prefix, uri_prefix, *_ = (y.strip() for y in x.split(" ", 2))
        idspaces[prefix] = uri_prefix

    #: CURIEs to typedefs
    typedefs: Mapping[ReferenceTuple, TypeDef] = {
        typedef.pair: typedef
        for typedef in iterate_typedefs(
            graph,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            macro_config=macro_config,
        )
    }

    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] = {
        synonym_typedef.pair: synonym_typedef
        for synonym_typedef in iterate_graph_synonym_typedefs(
            graph,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
        )
    }

    terms = _get_terms(
        graph,
        strict=strict,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        typedefs=typedefs,
        missing_typedefs=missing_typedefs,
        synonym_typedefs=synonym_typedefs,
        subset_typedefs=subset_typedefs,
        macro_config=macro_config,
        use_tqdm=use_tqdm,
    )

    return make_ad_hoc_ontology(
        _ontology=ontology_prefix,
        _name=name,
        _auto_generated_by=graph.graph.get("auto-generated-by"),
        _typedefs=list(typedefs.values()),
        _synonym_typedefs=list(synonym_typedefs.values()),
        _date=date,
        _data_version=data_version,
        _root_terms=root_terms,
        terms=terms,
        _property_values=property_values,
        _subsetdefs=subset_typedefs,
        _imports=imports,
        _idspaces=idspaces,
    )


def _get_terms(
    graph,
    *,
    strict: bool,
    ontology_prefix: str,
    upgrade: bool,
    typedefs: Mapping[ReferenceTuple, TypeDef],
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    subset_typedefs,
    missing_typedefs: set[ReferenceTuple],
    macro_config: MacroConfig,
    use_tqdm: bool = False,
) -> list[Term]:
    terms = []
    for reference, data in _iter_obo_graph(
        graph=graph,
        strict=strict,
        ontology_prefix=ontology_prefix,
        use_tqdm=use_tqdm,
        upgrade=upgrade,
    ):
        if reference.prefix != ontology_prefix:
            continue
        if not data:
            # this allows us to skip anything that isn't really defined
            # caveat: this misses terms that are just defined with an ID
            continue

        term = Term(
            reference=reference,
            builtin=_get_boolean(data, "builtin"),
            is_anonymous=_get_boolean(data, "is_anonymous"),
            is_obsolete=_get_boolean(data, "is_obsolete"),
            namespace=data.get("namespace"),
        )

        _process_alts(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_parents(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_synonyms(
            term,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            synonym_typedefs=synonym_typedefs,
        )
        _process_xrefs(
            term,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            macro_config=macro_config,
            upgrade=upgrade,
        )
        _process_properties(
            term,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            typedefs=typedefs,
        )
        _process_relations(
            term,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            typedefs=typedefs,
            missing_typedefs=missing_typedefs,
        )
        _process_replaced_by(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_subsets(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_intersection_of(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_union_of(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_equivalent_to(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_disjoint_from(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_consider(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_comment(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_description(term, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_creation_date(term, data)

        terms.append(term)
    return terms


def _process_description(term: Stanza, data, *, ontology_prefix: str, strict: bool):
    definition, definition_references = get_definition(
        data, node=term.reference, strict=strict, ontology_prefix=ontology_prefix
    )
    term.definition = definition
    if term.definition:
        for definition_reference in definition_references:
            term._append_annotation(
                v.has_description,
                OBOLiteral.string(term.definition),
                Annotation(v.has_dbxref, definition_reference),
            )


def _process_comment(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    if comment := data.get("comment"):
        term.append_comment(comment)


def _process_creation_date(term: Stanza, data) -> None:
    date_str = data.get("creation_date")
    if not date_str:
        return
    if isinstance(date_str, list):
        date_str = date_str[0]
    try:
        term.append_creation_date(date_str)
    except ValueError:
        logger.warning("[%s] failed to parse creation_date: %s", term.reference.curie, date_str)


def _process_union_of(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for reference in iterate_node_reference_tag(
        "union_of", data=data, ontology_prefix=ontology_prefix, strict=strict, node=term.reference
    ):
        term.append_union_of(reference)


def _process_equivalent_to(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for reference in iterate_node_reference_tag(
        "equivalent_to",
        data=data,
        ontology_prefix=ontology_prefix,
        strict=strict,
        node=term.reference,
    ):
        term.append_equivalent_to(reference)


def _process_disjoint_from(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for reference in iterate_node_reference_tag(
        "disjoint_from",
        data=data,
        ontology_prefix=ontology_prefix,
        strict=strict,
        node=term.reference,
    ):
        term.append_disjoint_from(reference)


def _process_alts(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for alt_reference in iterate_node_reference_tag(
        "alt_id", data, node=term.reference, strict=strict, ontology_prefix=ontology_prefix
    ):
        term.append_alt(alt_reference)


def _process_parents(term: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for tag in ["is_a", "instance_of"]:
        for parent in iterate_node_reference_tag(
            tag, data, node=term.reference, strict=strict, ontology_prefix=ontology_prefix
        ):
            term.append_parent(parent)


def _process_synonyms(
    term: Stanza,
    data,
    *,
    ontology_prefix: str,
    strict: bool,
    upgrade: bool,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
) -> None:
    synonyms = list(
        iterate_node_synonyms(
            data,
            synonym_typedefs,
            node=term.reference,
            strict=strict,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        )
    )
    for synonym in synonyms:
        term.append_synonym(synonym)


def _process_xrefs(
    term: Stanza,
    data,
    *,
    ontology_prefix: str,
    strict: bool,
    macro_config: MacroConfig,
    upgrade: bool,
) -> None:
    for reference, provenance in iterate_node_xrefs(
        data=data,
        strict=strict,
        ontology_prefix=ontology_prefix,
        node=term.reference,
        upgrade=upgrade,
    ):
        _handle_xref(term, reference, provenance=provenance, macro_config=macro_config)


def _process_properties(
    term: Stanza, data, *, ontology_prefix: str, strict: bool, upgrade: bool, typedefs
) -> None:
    for ann in iterate_node_properties(
        data,
        node=term.reference,
        strict=strict,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        context="stanza property",
    ):
        # TODO parse axioms
        term.append_property(ann)


def _process_relations(
    term: Stanza,
    data,
    *,
    ontology_prefix: str,
    strict: bool,
    upgrade: bool,
    typedefs: Mapping[ReferenceTuple, TypeDef],
    missing_typedefs: set[ReferenceTuple],
) -> None:
    relations_references = list(
        iterate_node_relationships(
            data,
            node=term.reference,
            strict=strict,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        )
    )
    for relation, reference in relations_references:
        if (
            relation.pair not in typedefs
            and relation.pair not in default_typedefs
            and relation.pair not in missing_typedefs
        ):
            missing_typedefs.add(relation.pair)
            logger.warning("[%s] has no typedef for %s", ontology_prefix, relation.curie)
            logger.debug("[%s] available typedefs: %s", ontology_prefix, set(typedefs))
        # TODO parse axioms
        term.append_relationship(relation, reference)


def _process_replaced_by(stanza: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for reference in iterate_node_reference_tag(
        "replaced_by", data, node=stanza.reference, strict=strict, ontology_prefix=ontology_prefix
    ):
        stanza.append_replaced_by(reference)


def _process_subsets(stanza: Stanza, data, *, ontology_prefix: str, strict: bool) -> None:
    for reference in iterate_node_reference_tag(
        "subset",
        data,
        node=stanza.reference,
        strict=strict,
        ontology_prefix=ontology_prefix,
        counter=SUBSET_ERROR_COUNTER,
    ):
        stanza.append_subset(reference)


def _get_boolean(data: Mapping[str, Any], tag: str) -> bool | None:
    value = data.get(tag)
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0]
    if value == "false":
        return False
    if value == "true":
        return True
    raise ValueError(value)


def _get_reference(
    data: Mapping[str, Any], tag: str, *, ontology_prefix: str, strict: bool, **kwargs
) -> Reference | None:
    value = data.get(tag)
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0]
    return _obo_parse_identifier(
        value, ontology_prefix=ontology_prefix, strict=strict, context=tag, **kwargs
    )


class MacroConfig:
    """A configuration data class for reader macros."""

    def __init__(
        self, data: Mapping[str, list[str]] | None = None, *, strict: bool, ontology_prefix: str
    ):
        """Instantiate the configuration from obonet graph metadata."""
        if data is None:
            data = {}

        self.treat_xrefs_as_equivalent: set[str] = set()
        for prefix in data.get("treat-xrefs-as-equivalent", []):
            prefix_norm = bioregistry.normalize_prefix(prefix)
            if prefix_norm is None:
                continue
            self.treat_xrefs_as_equivalent.add(prefix_norm)

        self.treat_xrefs_as_genus_differentia: dict[str, tuple[Reference, Reference]] = {}
        for line in data.get("treat-xrefs-as-genus-differentia", []):
            try:
                gd_prefix, gd_predicate, gd_target = line.split()
            except ValueError:
                # this happens in `plana`, where there's an incorrectly written
                # line `CARO part_of NCBITaxon:79327; CL part_of NCBITaxon:79327`
                tqdm.write(
                    f"[{ontology_prefix}] failed to parse treat-xrefs-as-genus-differentia: {line}"
                )
                continue

            gd_prefix_norm = bioregistry.normalize_prefix(gd_prefix)
            if gd_prefix_norm is None:
                continue
            gd_predicate_re = _obo_parse_identifier(
                gd_predicate, ontology_prefix=ontology_prefix, strict=strict
            )
            if gd_predicate_re is None:
                continue
            gd_target_re = _obo_parse_identifier(
                gd_target, ontology_prefix=ontology_prefix, strict=strict
            )
            if gd_target_re is None:
                continue
            self.treat_xrefs_as_genus_differentia[gd_prefix_norm] = (gd_predicate_re, gd_target_re)

        self.treat_xrefs_as_relationship: dict[str, Reference] = {}
        for line in data.get("treat-xrefs-as-relationship", []):
            try:
                gd_prefix, gd_predicate = line.split()
            except ValueError:
                tqdm.write(
                    f"[{ontology_prefix}] failed to parse treat-xrefs-as-relationship: {line}"
                )
                continue

            gd_prefix_norm = bioregistry.normalize_prefix(gd_prefix)
            if gd_prefix_norm is None:
                continue
            gd_predicate_re = _obo_parse_identifier(
                gd_predicate, ontology_prefix=ontology_prefix, strict=strict
            )
            if gd_predicate_re is None:
                continue
            self.treat_xrefs_as_relationship[gd_prefix_norm] = gd_predicate_re

        self.treat_xrefs_as_is_a: set[str] = set()
        for prefix in data.get("treat-xrefs-as-is_a", []):
            gd_prefix_norm = bioregistry.normalize_prefix(prefix)
            if gd_prefix_norm is None:
                continue
            self.treat_xrefs_as_is_a.add(gd_prefix_norm)


def _handle_xref(
    term: Stanza,
    xref: Reference,
    *,
    provenance: list[Reference | OBOLiteral],
    macro_config: MacroConfig | None = None,
) -> Stanza:
    annotations = [Annotation(v.has_dbxref, p) for p in provenance]

    if macro_config is not None:
        if xref.prefix in macro_config.treat_xrefs_as_equivalent:
            return term.append_equivalent(xref, annotations=annotations)
        elif object_property := macro_config.treat_xrefs_as_genus_differentia.get(xref.prefix):
            # TODO how to add annotations here?
            if annotations:
                logger.warning(
                    "[%s] unable to add provenance to xref upgraded to intersection_of: %s",
                    term.reference.curie,
                    xref,
                )
            return term.append_intersection_of(xref).append_intersection_of(object_property)
        elif predicate := macro_config.treat_xrefs_as_relationship.get(xref.prefix):
            return term.append_relationship(predicate, xref, annotations=annotations)
        elif xref.prefix in macro_config.treat_xrefs_as_is_a:
            return term.append_parent(xref, annotations=annotations)

    # TODO this is not what spec calls for, maybe
    #  need a flag in macro config for this
    if xref.prefix in PROVENANCE_PREFIXES:
        return term.append_provenance(xref, annotations=annotations)

    return term.append_xref(xref, annotations=annotations)


SUBSET_ERROR_COUNTER: Counter[tuple[str, str]] = Counter()


def _get_subsetdefs(graph: nx.MultiDiGraph, ontology_prefix: str) -> list[tuple[Reference, str]]:
    rv = []
    for subsetdef in graph.get("subsetdef", []):
        left, _, right = subsetdef.partition(" ")
        if not right:
            logger.warning("[%s] subsetdef did not have two parts", ontology_prefix, subsetdef)
            continue
        left_ref = _obo_parse_identifier(
            left,
            ontology_prefix=ontology_prefix,
            name=right,
            line=subsetdef,
            counter=SUBSET_ERROR_COUNTER,
        )
        if left_ref is None:
            continue
        right = right.strip('"')
        rv.append((left_ref, right))
    return rv


def _clean_graph_ontology(graph, prefix: str) -> None:
    """Update the ontology entry in the graph's metadata, if necessary."""
    if "ontology" not in graph.graph:
        logger.debug('[%s] missing "ontology" key', prefix)
        graph.graph["ontology"] = prefix
    elif not graph.graph["ontology"].isalpha():
        logger.debug(
            "[%s] ontology prefix `%s` has a strange format. replacing with prefix",
            prefix,
            graph.graph["ontology"],
        )
        graph.graph["ontology"] = prefix


def _clean_graph_version(
    graph, ontology_prefix: str, version: str | None, date: datetime | None
) -> str | None:
    if ontology_prefix in STATIC_VERSION_REWRITES:
        return STATIC_VERSION_REWRITES[ontology_prefix]

    data_version: str | None = graph.graph.get("data-version") or None
    if version:
        clean_injected_version = cleanup_version(version, prefix=ontology_prefix)
        if not data_version:
            logger.debug(
                "[%s] did not have a version, overriding with %s",
                ontology_prefix,
                clean_injected_version,
            )
            return clean_injected_version

        clean_data_version = cleanup_version(data_version, prefix=ontology_prefix)
        if clean_data_version != clean_injected_version:
            # in this case, we're going to trust the one that's passed
            # through explicitly more than the graph's content
            logger.debug(
                "[%s] had version %s, overriding with %s", ontology_prefix, data_version, version
            )
        return clean_injected_version

    if data_version:
        clean_data_version = cleanup_version(data_version, prefix=ontology_prefix)
        logger.debug("[%s] using version %s", ontology_prefix, clean_data_version)
        return clean_data_version

    if date is not None:
        derived_date_version = date.strftime("%Y-%m-%d")
        logger.debug(
            "[%s] does not report a version. falling back to date: %s",
            ontology_prefix,
            derived_date_version,
        )
        return derived_date_version

    logger.debug("[%s] does not report a version nor a date", ontology_prefix)
    return None


def _iter_obo_graph(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = False,
    ontology_prefix: str,
    use_tqdm: bool = False,
    upgrade: bool,
) -> Iterable[tuple[Reference, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in tqdm(
        graph.nodes(data=True), disable=not use_tqdm, unit_scale=True, desc=f"[{ontology_prefix}]"
    ):
        name = data.get("name")
        match _parse_str_or_curie_or_uri_helper(
            node,
            ontology_prefix=ontology_prefix,
            name=name,
            upgrade=upgrade,
            context="stanza ID",
        ):
            case Reference() as reference:
                yield reference, data
            case NotCURIEError() as exc:
                if _is_valid_identifier(node):
                    yield default_reference(ontology_prefix, node, name=name), data
                elif strict:
                    raise exc
                else:
                    logger.warning(str(exc))
            case ParseError() as exc:
                if strict:
                    raise exc
                else:
                    logger.warning(str(exc))
            # if blacklisted, just skip it with no warning


def _get_date(graph, ontology_prefix: str) -> datetime | None:
    try:
        rv = datetime.strptime(graph.graph["date"], DATE_FORMAT)
    except KeyError:
        logger.info("[%s] does not report a date", ontology_prefix)
        return None
    except ValueError:
        logger.info(
            "[%s] reports a date that can't be parsed: %s", ontology_prefix, graph.graph["date"]
        )
        return None
    else:
        return rv


def _get_name(graph, ontology_prefix: str) -> str:
    try:
        rv = graph.graph["name"]
    except KeyError:
        logger.info("[%s] does not report a name", ontology_prefix)
        rv = ontology_prefix
    return rv


def iterate_graph_synonym_typedefs(
    graph: nx.MultiDiGraph, *, ontology_prefix: str, strict: bool = False, upgrade: bool
) -> Iterable[SynonymTypeDef]:
    """Get synonym type definitions from an :mod:`obonet` graph."""
    for line in graph.graph.get("synonymtypedef", []):
        # TODO handle trailing comments
        line, _, specificity = (x.strip() for x in line.rpartition('"'))
        specificity = specificity.upper()
        if not specificity:
            specificity = None
        elif specificity not in t.get_args(SynonymScope):
            if strict:
                raise ValueError(f"invalid synonym specificty: {specificity}")
            logger.warning("[%s] invalid synonym specificty: %s", ontology_prefix, specificity)
            specificity = None

        curie, name = line.split(" ", 1)
        # the name should be in quotes, so strip them out
        name = name.strip().strip('"')
        # TODO unquote the string?
        reference = _obo_parse_identifier(
            curie,
            ontology_prefix=ontology_prefix,
            name=name,
            upgrade=upgrade,
            strict=strict,
        )
        if reference is None:
            logger.warning("[%s] unable to parse synonym typedef ID %s", ontology_prefix, curie)
            continue
        yield SynonymTypeDef(reference=reference, specificity=specificity)


def iterate_typedefs(
    graph: nx.MultiDiGraph,
    *,
    ontology_prefix: str,
    strict: bool = False,
    upgrade: bool,
    macro_config: MacroConfig | None = None,
) -> Iterable[TypeDef]:
    """Get type definitions from an :mod:`obonet` graph."""
    if macro_config is None:
        macro_config = MacroConfig(strict=strict, ontology_prefix=ontology_prefix)
    # can't really have a pre-defined set of synonym typedefs here!
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef] = {}
    typedefs: Mapping[ReferenceTuple, TypeDef] = {}
    missing_typedefs: set[ReferenceTuple] = set()
    for data in graph.graph.get("typedefs", []):
        if "id" in data:
            typedef_id = data["id"]
        elif "identifier" in data:
            typedef_id = data["identifier"]
        else:
            raise KeyError("typedef is missing an `id`")

        name = data.get("name")
        if name is None:
            logger.debug("[%s] typedef %s is missing a name", ontology_prefix, typedef_id)

        reference = _obo_parse_identifier(
            typedef_id, strict=strict, ontology_prefix=ontology_prefix, name=name, upgrade=upgrade
        )
        if reference is None:
            logger.warning("[%s] unable to parse typedef ID %s", ontology_prefix, typedef_id)
            continue

        typedef = TypeDef(
            reference=reference,
            namespace=data.get("namespace"),
            is_metadata_tag=_get_boolean(data, "is_metadata_tag"),
            is_class_level=_get_boolean(data, "is_class_level"),
            builtin=_get_boolean(data, "builtin"),
            is_obsolete=_get_boolean(data, "is_obsolete"),
            is_anonymous=_get_boolean(data, "is_anonymous"),
            is_anti_symmetric=_get_boolean(data, "is_anti_symmetric"),
            is_symmetric=_get_boolean(data, "is_symmetric"),
            is_reflexive=_get_boolean(data, "is_reflexive"),
            is_cyclic=_get_boolean(data, "is_cyclic"),
            is_transitive=_get_boolean(data, "is_transitive"),
            is_functional=_get_boolean(data, "is_functional"),
            is_inverse_functional=_get_boolean(data, "is_inverse_functional"),
            domain=_get_reference(data, "domain", ontology_prefix=ontology_prefix, strict=strict),
            range=_get_reference(data, "range", ontology_prefix=ontology_prefix, strict=strict),
            inverse=_get_reference(
                data, "inverse_of", ontology_prefix=ontology_prefix, strict=strict
            ),
        )
        _process_alts(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_parents(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_synonyms(
            typedef,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            synonym_typedefs=synonym_typedefs,
        )
        _process_xrefs(
            typedef,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            macro_config=macro_config,
            upgrade=upgrade,
        )
        _process_properties(
            typedef,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            typedefs=typedefs,
        )
        _process_relations(
            typedef,
            data,
            ontology_prefix=ontology_prefix,
            strict=strict,
            upgrade=upgrade,
            typedefs=typedefs,
            missing_typedefs=missing_typedefs,
        )
        _process_replaced_by(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_subsets(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_intersection_of(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_union_of(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_equivalent_to(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_disjoint_from(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_consider(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_comment(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_description(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_creation_date(typedef, data)

        # the next 4 are typedef-specific
        _process_equivalent_to_chain(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        _process_holds_over_chain(typedef, data, ontology_prefix=ontology_prefix, strict=strict)
        typedef.disjoint_over.extend(
            iterate_node_reference_tag(
                "disjoint_over",
                data,
                node=typedef.reference,
                ontology_prefix=ontology_prefix,
                strict=strict,
            )
        )
        typedef.transitive_over.extend(
            iterate_node_reference_tag(
                "transitive_over",
                data,
                node=typedef.reference,
                ontology_prefix=ontology_prefix,
                strict=strict,
            )
        )

        yield typedef


def _process_consider(stanza: Stanza, data, *, ontology_prefix: str, strict: bool = False):
    for reference in iterate_node_reference_tag(
        "consider",
        data,
        node=stanza.reference,
        ontology_prefix=ontology_prefix,
        strict=strict,
    ):
        stanza.append_see_also(reference)


def _process_equivalent_to_chain(
    typedef: TypeDef, data, *, ontology_prefix: str, strict: bool = False
) -> None:
    for chain in _iterate_chain(
        "equivalent_to_chain", typedef, data, ontology_prefix=ontology_prefix, strict=strict
    ):
        typedef.equivalent_to_chain.append(chain)


def _process_holds_over_chain(
    typedef: TypeDef, data, *, ontology_prefix: str, strict: bool = False
) -> None:
    for chain in _iterate_chain(
        "holds_over_chain", typedef, data, ontology_prefix=ontology_prefix, strict=strict
    ):
        typedef.holds_over_chain.append(chain)


def _iterate_chain(
    tag: str, typedef: TypeDef, data, *, ontology_prefix: str, strict: bool = False
) -> Iterable[list[Reference]]:
    for chain in data.get(tag, []):
        # chain is a list of CURIEs
        predicate_chain = _process_chain_helper(typedef, chain, ontology_prefix=ontology_prefix)
        if predicate_chain is None:
            logger.warning(
                "[%s - %s] could not parse line: %s: %s",
                ontology_prefix,
                typedef.curie,
                tag,
                chain,
            )
        else:
            yield predicate_chain


def _process_chain_helper(
    term: Stanza, chain: str, ontology_prefix: str, strict: bool = False
) -> list[Reference] | None:
    rv = []
    for curie in chain.split():
        curie = curie.strip()
        r = _obo_parse_identifier(
            curie, ontology_prefix=ontology_prefix, strict=strict, node=term.reference
        )
        if r is None:
            return None
        rv.append(r)
    return rv


def get_definition(
    data, *, node: Reference, ontology_prefix: str, strict: bool = False
) -> tuple[None | str, list[Reference | OBOLiteral]]:
    """Extract the definition from the data."""
    definition = data.get("def")  # it's allowed not to have a definition
    if not definition:
        return None, []
    return _extract_definition(
        definition, node=node, strict=strict, ontology_prefix=ontology_prefix
    )


def _extract_definition(
    s: str,
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
) -> tuple[None | str, list[Reference | OBOLiteral]]:
    """Extract the definitions."""
    if not s.startswith('"'):
        logger.warning(f"[{node.curie}] definition does not start with a quote")
        return None, []

    try:
        definition, rest = _quote_split(s)
    except ValueError as e:
        logger.warning("[%s] failed to parse definition quotes: %s", node.curie, str(e))
        return None, []

    if not rest.startswith("["):
        logger.debug("[%s] no square brackets for provenance on line: %s", node.curie, s)
        provenance = []
    else:
        rest = rest.lstrip("[").rstrip("]")  # FIXME this doesn't account for trailing annotations
        provenance = _parse_provenance_list(
            rest,
            node=node,
            ontology_prefix=ontology_prefix,
            counter=DEFINITION_PROVENANCE_COUNTER,
            scope_text="definition provenance",
            line=s,
            strict=strict,
        )
    return definition or None, provenance


def get_first_nonescaped_quote(s: str) -> int | None:
    """Get the first non-escaped quote."""
    if not s:
        return None
    if s[0] == '"':
        # special case first position
        return 0
    for i, (a, b) in enumerate(pairwise(s), start=1):
        if b == '"' and a != "\\":
            return i
    return None


def _quote_split(s: str) -> tuple[str, str]:
    if not s.startswith('"'):
        raise ValueError(f"'{s}' does not start with a quote")
    s = s.removeprefix('"')
    i = get_first_nonescaped_quote(s)
    if i is None:
        raise ValueError(f"no closing quote found in `{s}`")
    return _clean_definition(s[:i].strip()), s[i + 1 :].strip()


def _clean_definition(s: str) -> str:
    # if '\t' in s:
    #     logger.warning('has tab')
    return s.replace('\\"', '"').replace("\n", " ").replace("\t", " ").replace(r"\d", "")


def _extract_synonym(
    s: str,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool,
) -> Synonym | None:
    # TODO check if the synonym is written like a CURIE... it shouldn't but I've seen it happen
    try:
        name, rest = _quote_split(s)
    except ValueError:
        logger.warning("[%s] invalid synonym: %s", node.curie, s)
        return None

    specificity, rest = _chomp_specificity(rest)
    synonym_typedef, rest = _chomp_typedef(
        rest,
        synonym_typedefs=synonym_typedefs,
        strict=strict,
        node=node,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
    )
    provenance, rest = _chomp_references(
        rest,
        strict=strict,
        node=node,
        ontology_prefix=ontology_prefix,
        line=s,
    )
    annotations = _chomp_axioms(rest, node=node, strict=strict)

    return Synonym(
        name=name,
        specificity=specificity,
        type=synonym_typedef.reference if synonym_typedef else None,
        provenance=list(provenance or []),
        annotations=annotations,
    )


#: A counter for errors in parsing provenance
DEFINITION_PROVENANCE_COUNTER: Counter[tuple[str, str]] = Counter()


def iterate_node_synonyms(
    data: Mapping[str, Any],
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool,
) -> Iterable[Synonym]:
    """Extract synonyms from a :mod:`obonet` node's data.

    Example strings

    - "LTEC I" EXACT [Orphanet:93938,DOI:xxxx]
    - "LTEC I" EXACT [Orphanet:93938]
    - "LTEC I" [Orphanet:93938]
    - "LTEC I" []
    """
    for s in data.get("synonym", []):
        s = _extract_synonym(
            s,
            synonym_typedefs,
            node=node,
            strict=strict,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        )
        if s is not None:
            yield s


def iterate_node_properties(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool,
    context: str,
) -> Iterable[Annotation]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get("property_value", []):
        if yv := _handle_prop(
            prop_value_type,
            node=node,
            strict=strict,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
            context=context,
        ):
            yield yv


#: Keep track of property-value pairs for which the value couldn't be parsed,
#: such as `dc:conformsTo autoimmune:inflammation.yaml` in MONDO
UNHANDLED_PROP_OBJECTS: Counter[tuple[str, str]] = Counter()

UNHANDLED_PROPS: Counter[tuple[str, str]] = Counter()


def _handle_prop(
    prop_value_type: str,
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool,
    context: str | None,
) -> Annotation | None:
    try:
        prop, value_type = prop_value_type.split(" ", 1)
    except ValueError:
        logger.warning("[%s] property_value is missing a space: %s", node.curie, prop_value_type)
        return None

    prop_reference = _get_prop(
        prop,
        node=node,
        strict=strict,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        line=prop_value_type,
        counter=UNHANDLED_PROPS,
        context=context,
    )
    if prop_reference is None:
        return None

    value_type = value_type.strip()
    datatype: Reference | None
    if " " not in value_type:
        value, datatype = value_type, None
    else:
        value, datatype_raw = (s.strip() for s in value_type.rsplit(" ", 1))
        match _parse_str_or_curie_or_uri_helper(
            datatype_raw,
            ontology_prefix=ontology_prefix,
            node=node,
            predicate=prop_reference,
            line=prop_value_type,
            upgrade=upgrade,
            context="property datatype",
        ):
            case Reference() as datatype_:
                datatype = datatype_
            case BlocklistError():
                return None
            case ParseError() as exc:
                if strict:
                    raise exc
                else:
                    logger.warning(str(exc))
                    return None

    # if it's an empty string, like the ones removed in https://github.com/oborel/obo-relations/pull/830,
    # just quit
    if value == '""':
        return None

    quoted = value.startswith('"') and value.endswith('"')
    value = value.strip('"').strip()

    # first, special case datetimes. Whether it's quoted or not,
    # we always deal with this first
    if datatype and datatype.curie == "xsd:dateTime":
        try:
            obo_literal = OBOLiteral.datetime(value)
        except ValueError:
            logger.warning(
                "[%s - %s] could not parse date: %s", node.curie, prop_reference.curie, value
            )
            return None
        else:
            return Annotation(prop_reference, obo_literal)

    if datatype and datatype.curie == "xsd:anyURI":
        match _parse_str_or_curie_or_uri_helper(
            value,
            node=node,
            predicate=prop_reference,
            ontology_prefix=ontology_prefix,
            line=prop_value_type,
            upgrade=upgrade,
            context="property object",
        ):
            case Reference() as obj_reference:
                return Annotation(prop_reference, obj_reference)
            case BlocklistError():
                return None
            case UnparsableIRIError():
                return Annotation(prop_reference, OBOLiteral.uri(value))
            case ParseError() as exc:
                if strict:
                    raise exc
                else:
                    logger.warning(str(exc))
                    return None

    # if it's quoted and there's a data try parsing as a CURIE/URI anyway (this is a bit
    # aggressive, but more useful than spec).
    if quoted:
        # give a try parsing it anyway, just in case ;)
        match _parse_str_or_curie_or_uri_helper(
            value,
            ontology_prefix=ontology_prefix,
            node=node,
            line=prop_value_type,
            upgrade=upgrade,
            predicate=prop_reference,
            context="property object",
        ):
            case Reference() as obj_reference:
                return Annotation(prop_reference, obj_reference)
            case BlocklistError():
                return None
            case ParseError():
                if datatype:
                    return Annotation(prop_reference, OBOLiteral(value, datatype, None))
                else:
                    return Annotation(prop_reference, OBOLiteral.string(value))
    else:
        if datatype:
            logger.debug(
                "[%s] throwing away datatype since no quotes were used: %s", node.curie, value_type
            )

        # if it wasn't quoted and there was no datatype, go for parsing as an object
        match _obo_parse_identifier(
            value,
            strict=strict,
            ontology_prefix=ontology_prefix,
            node=node,
            predicate=prop_reference,
            line=prop_value_type,
            context="property object",
            counter=UNHANDLED_PROP_OBJECTS,
        ):
            case Reference() as obj_reference:
                return Annotation(prop_reference, obj_reference)
            case None:
                return None

    return None


def _get_prop(
    property_id: str,
    *,
    node: Reference,
    strict: bool,
    ontology_prefix: str,
    upgrade: bool,
    line: str,
    counter: Counter[tuple[str, str]] | None = None,
    context: str | None = None,
) -> Reference | None:
    if rv := _parse_default_prop(property_id, ontology_prefix):
        return rv
    return _obo_parse_identifier(
        property_id,
        strict=strict,
        node=node,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        counter=counter,
        context=context,
        line=line,
    )


def _parse_default_prop(property_id, ontology_prefix) -> Reference | None:
    for delim in "#/":
        sw = f"http://purl.obolibrary.org/obo/{ontology_prefix}{delim}"
        if property_id.startswith(sw):
            identifier = property_id.removeprefix(sw)
            return default_reference(ontology_prefix, identifier)
    return None


def iterate_node_reference_tag(
    tag: str,
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool = True,
    counter: Counter[tuple[str, str]] | None = None,
) -> Iterable[Reference]:
    """Extract a list of CURIEs from the data."""
    for identifier in data.get(tag, []):
        reference = _obo_parse_identifier(
            identifier,
            strict=strict,
            node=node,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
            counter=counter,
        )
        if reference is None:
            logger.warning(
                "[%s] %s - could not parse identifier: %s", ontology_prefix, tag, identifier
            )
        else:
            yield reference


def _process_intersection_of(
    term: Stanza,
    data: Mapping[str, Any],
    *,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool = True,
) -> None:
    """Extract a list of CURIEs from the data."""
    for line in data.get("intersection_of", []):
        predicate_id, _, target_id = line.partition(" ")
        predicate = _obo_parse_identifier(
            predicate_id,
            strict=strict,
            node=term.reference,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        )
        if predicate is None:
            logger.warning("[%s] - could not parse intersection_of: %s", ontology_prefix, line)
            continue

        if target_id:
            # this means that there's a second part, so let's try parsing it
            target = _obo_parse_identifier(
                target_id,
                strict=strict,
                node=term.reference,
                predicate=predicate,
                ontology_prefix=ontology_prefix,
                upgrade=upgrade,
            )
            if target is None:
                logger.warning(
                    "[%s] could not parse intersection_of target: %s", ontology_prefix, line
                )
                continue
            term.append_intersection_of(predicate, target)
        else:
            term.append_intersection_of(predicate)


def iterate_node_relationships(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = False,
    ontology_prefix: str,
    upgrade: bool,
) -> Iterable[tuple[Reference, Reference]]:
    """Extract relationships from a :mod:`obonet` node's data."""
    for line in data.get("relationship", []):
        relation_curie, target_curie = line.split(" ")

        predicate = _obo_parse_identifier(
            relation_curie,
            strict=strict,
            ontology_prefix=ontology_prefix,
            node=node,
            upgrade=upgrade,
            line=line,
            context="relationship predicate",
        )
        match predicate:
            # TODO extend with other exception handling
            case None:
                logger.warning("[%s] could not parse relation %s", node.curie, relation_curie)
                continue

        match _parse_str_or_curie_or_uri_helper(
            target_curie,
            ontology_prefix=ontology_prefix,
            node=node,
            predicate=predicate,
            line=line,
            context="relationship target",
            upgrade=upgrade,
        ):
            case Reference() as target:
                yield predicate, target
            case ParseError() as exc:
                if strict:
                    raise exc
                else:
                    logger.warning(str(exc))


def iterate_node_xrefs(
    *,
    data: Mapping[str, Any],
    strict: bool = False,
    ontology_prefix: str,
    node: Reference,
    upgrade: bool,
) -> Iterable[tuple[Reference, list[Reference | OBOLiteral]]]:
    """Extract xrefs from a :mod:`obonet` node's data."""
    for line in data.get("xref", []):
        line = line.strip()
        if pair := _parse_xref_line(
            line.strip(),
            strict=strict,
            node=node,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        ):
            yield pair


def _parse_xref_line(
    line: str, *, strict: bool = False, ontology_prefix: str, node: Reference, upgrade: bool
) -> tuple[Reference, list[Reference | OBOLiteral]] | None:
    xref, _, rest = line.partition(" [")

    rules = get_rules()

    if rules.str_is_blocked(xref, context=ontology_prefix) or ":" not in xref:
        return None  # sometimes xref to self... weird

    xref = rules.remap_prefix(xref, context=ontology_prefix)

    split_space = " " in xref
    if split_space:
        _xref_split = xref.split(" ", 1)
        if _xref_split[1][0] not in {'"', "("}:
            logger.debug("[%s] Problem with space in xref %s", node.curie, xref)
            return None
        xref = _xref_split[0]

    xref_ref = _parse_str_or_curie_or_uri_helper(
        xref, ontology_prefix=ontology_prefix, node=node, line=line, context="xref", upgrade=upgrade
    )
    match xref_ref:
        case BlocklistError():
            return None
        case ParseError() as exc:
            if strict:
                raise exc
            else:
                if not XREF_PROVENANCE_COUNTER[ontology_prefix, xref]:
                    logger.warning(str(exc))
                XREF_PROVENANCE_COUNTER[ontology_prefix, xref] += 1
                return None

    if rest:
        rest_front, _, _rest_rest = rest.partition("]")
        provenance = _parse_provenance_list(
            rest_front,
            node=node,
            ontology_prefix=ontology_prefix,
            counter=XREF_PROVENANCE_COUNTER,
            scope_text="xref provenance",
            line=line,
            strict=strict,
        )
    else:
        provenance = []

    return xref_ref, provenance


XREF_PROVENANCE_COUNTER: Counter[tuple[str, str]] = Counter()
