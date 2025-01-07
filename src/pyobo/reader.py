"""OBO Readers."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import bioregistry
import networkx as nx
from curies import ReferenceTuple
from more_itertools import pairwise
from tqdm.auto import tqdm

from .constants import DATE_FORMAT, PROVENANCE_PREFIXES
from .reader_utils import (
    _chomp_axioms,
    _chomp_references,
    _chomp_specificity,
    _chomp_typedef,
)
from .registries import curie_has_blacklisted_prefix, curie_is_blacklisted, remap_prefix
from .struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    TypeDef,
    default_reference,
    make_ad_hoc_ontology,
)
from .struct.reference import OBOLiteral, _parse_identifier
from .struct.struct_utils import Annotation, Stanza
from .struct.typedef import default_typedefs, has_ontology_root_term
from .utils.misc import STATIC_VERSION_REWRITES, cleanup_version

__all__ = [
    "from_obo_path",
    "from_obonet",
]

logger = logging.getLogger(__name__)


def from_obo_path(
    path: str | Path,
    prefix: str | None = None,
    *,
    strict: bool = True,
    version: str | None,
    upgrade: bool = True,
) -> Obo:
    """Get the OBO graph from a path."""
    path = Path(path).expanduser().resolve()
    if path.suffix.endswith(".gz"):
        import gzip

        logger.info("[%s] parsing gzipped OBO with obonet from %s", prefix or "<unknown>", path)
        with gzip.open(path, "rt") as file:
            graph = _read_obo(file, prefix)
    elif path.suffix.endswith(".zip"):
        import io
        import zipfile

        logger.info("[%s] parsing zipped OBO with obonet from %s", prefix or "<unknown>", path)
        with zipfile.ZipFile(path) as zf:
            with zf.open(path.name.removesuffix(".zip"), "r") as file:
                content = file.read().decode("utf-8")
                graph = _read_obo(io.StringIO(content), prefix)
    else:
        logger.info("[%s] parsing OBO with obonet from %s", prefix or "<unknown>", path)
        with open(path) as file:
            graph = _read_obo(file, prefix)

    if prefix:
        # Make sure the graph is named properly
        _clean_graph_ontology(graph, prefix)

    # Convert to an Obo instance and return
    return from_obonet(graph, strict=strict, version=version, upgrade=upgrade)


def _read_obo(filelike, prefix: str | None) -> nx.MultiDiGraph:
    import obonet

    return obonet.read_obo(
        tqdm(
            filelike,
            unit_scale=True,
            desc=f'[{prefix or ""}] parsing OBO',
            disable=None,
            leave=True,
        ),
        # TODO this is the default, turn it off and see what happens
        ignore_obsolete=True,
    )


def _normalize_prefix_strict(prefix: str) -> str:
    n = bioregistry.normalize_prefix(prefix)
    if n is None:
        raise ValueError(f"unknown prefix: {prefix}")
    return n


def from_obonet(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
    version: str | None = None,
    upgrade: bool = True,
) -> Obo:
    """Get all of the terms from a OBO graph."""
    ontology_prefix_raw = graph.graph["ontology"]
    ontology_prefix = _normalize_prefix_strict(ontology_prefix_raw)
    logger.info("[%s] extracting OBO using obonet", ontology_prefix)

    date = _get_date(graph=graph, ontology_prefix=ontology_prefix)
    name = _get_name(graph=graph, ontology_prefix=ontology_prefix)

    macro_config = MacroConfig(graph.graph, strict=strict, ontology_prefix=ontology_prefix)

    data_version = _clean_graph_version(
        graph, ontology_prefix=ontology_prefix, version=version, date=date
    )
    if data_version and "/" in data_version:
        raise ValueError(
            f"[{ontology_prefix}] slashes not allowed in data versions because of filesystem usage: {data_version}"
        )

    root_terms: list[Reference] = []
    property_values: list[Annotation] = []
    for t in iterate_node_properties(
        graph.graph,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
        node=Reference(prefix="obo", identifier=ontology_prefix),
    ):
        if t.predicate.pair == has_ontology_root_term.pair:
            match t.value:
                case OBOLiteral():
                    raise RuntimeError
                case Reference():
                    root_terms.append(t.value)
        else:
            property_values.append(t)

    #: CURIEs to typedefs
    typedefs: Mapping[ReferenceTuple, TypeDef] = {
        typedef.pair: typedef
        for typedef in iterate_graph_typedefs(
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

    missing_typedefs: set[ReferenceTuple] = set()
    terms = []
    n_alt_ids, n_parents, n_synonyms, n_relations, n_properties, n_xrefs = 0, 0, 0, 0, 0, 0
    n_references = 0
    for reference, data in _iter_obo_graph(
        graph=graph, strict=strict, ontology_prefix=ontology_prefix
    ):
        if reference.prefix != ontology_prefix or not data:
            continue
        n_references += 1

        provenance = []
        definition, definition_references = get_definition(
            data, node=reference, strict=strict, ontology_prefix=ontology_prefix
        )
        provenance.extend(definition_references)

        alt_ids = list(
            iterate_node_alt_ids(
                data, node=reference, strict=strict, ontology_prefix=ontology_prefix
            )
        )
        n_alt_ids += len(alt_ids)

        parents = list(
            iterate_node_parents(
                data, node=reference, strict=strict, ontology_prefix=ontology_prefix
            )
        )
        n_parents += len(parents)

        synonyms = list(
            iterate_node_synonyms(
                data,
                synonym_typedefs,
                node=reference,
                strict=strict,
                ontology_prefix=ontology_prefix,
                upgrade=upgrade,
            )
        )
        n_synonyms += len(synonyms)

        term = Term(
            reference=reference,
            definition=definition,
            parents=parents,
            synonyms=synonyms,
            provenance=provenance,
            alt_ids=alt_ids,
            builtin=_get_boolean(data, "builtin"),
            is_anonymous=_get_boolean(data, "is_anonymous"),
            is_obsolete=_get_boolean(data, "is_obsolete"),
        )

        node_xrefs: list[Reference] = list(
            iterate_node_xrefs(
                data=data,
                strict=strict,
                ontology_prefix=ontology_prefix,
                node=reference,
            )
        )
        for node_xref in node_xrefs:
            _handle_xref(term, node_xref, macro_config=macro_config)

        relations_references = list(
            iterate_node_relationships(
                data,
                node=reference,
                strict=strict,
                ontology_prefix=ontology_prefix,
                upgrade=upgrade,
            )
        )
        for relation, reference in relations_references:
            if relation.pair in typedefs:
                typedef = typedefs[relation.pair]
            elif relation.pair in default_typedefs:
                typedef = default_typedefs[relation.pair]
            else:
                if relation.pair not in missing_typedefs:
                    missing_typedefs.add(relation.pair)
                    logger.warning("[%s] has no typedef for %s", ontology_prefix, relation)
                    logger.debug("[%s] available typedefs: %s", ontology_prefix, set(typedefs))
                continue
            n_relations += 1
            term.append_relationship(typedef, reference)

        for t in iterate_node_properties(
            data, node=reference, strict=strict, ontology_prefix=ontology_prefix, upgrade=upgrade
        ):
            n_properties += 1
            term.append_property(t)

        if comment := data.get("comment"):
            term.append_comment(comment)

        for replaced_by in data.get("replaced_by", []):
            rr = _parse_identifier(
                replaced_by, ontology_prefix=ontology_prefix, strict=strict, node=reference
            )
            if rr is None:
                continue
            term.append_replaced_by(rr)

        terms.append(term)

    subset_typedefs = _get_subsetdefs(graph.graph, ontology_prefix=ontology_prefix)

    logger.info(
        f"[{ontology_prefix}] got {n_references:,} references, {len(typedefs):,} typedefs, {len(terms):,} terms,"
        f" {n_alt_ids:,} alt ids, {n_parents:,} parents, {n_synonyms:,} synonyms, {n_xrefs:,} xrefs,"
        f" {n_relations:,} relations, {n_properties:,} properties, and {len(subset_typedefs)} subset typedefs.",
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
    )


def _get_boolean(data, tag) -> bool | None:
    value = data.get(tag)
    if value is None:
        return None
    if value == "false":
        return False
    if value == "true":
        return True
    raise ValueError(value)


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

        self.treat_xrefs_as_genus_differentia: dict[str, Annotation] = {}
        for line in data.get("treat-xrefs-as-genus-differentia", []):
            gd_prefix, gd_predicate, gd_target = line.split()
            gd_prefix_norm = bioregistry.normalize_prefix(gd_prefix)
            if gd_prefix_norm is None:
                continue
            gd_predicate_re = _parse_identifier(
                gd_predicate, ontology_prefix=ontology_prefix, strict=strict
            )
            if gd_predicate_re is None:
                continue
            gd_target_re = _parse_identifier(
                gd_target, ontology_prefix=ontology_prefix, strict=strict
            )
            if gd_target_re is None:
                continue
            self.treat_xrefs_as_genus_differentia[gd_prefix_norm] = Annotation(
                gd_predicate_re, gd_target_re
            )

        self.treat_xrefs_as_relationship: dict[str, Reference] = {}
        for line in data.get("treat-xrefs-as-relationship", []):
            gd_prefix, gd_predicate = line.split()
            gd_prefix_norm = bioregistry.normalize_prefix(gd_prefix)
            if gd_prefix_norm is None:
                continue
            gd_predicate_re = _parse_identifier(
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
    macro_config: MacroConfig | None = None,
) -> Stanza:
    if macro_config is not None:
        if xref.prefix in macro_config.treat_xrefs_as_equivalent:
            return term.append_equivalent(xref)
        elif object_property := macro_config.treat_xrefs_as_genus_differentia.get(xref.prefix):
            return term.append_intersection_of(xref).append_intersection_of(object_property)
        elif predicate := macro_config.treat_xrefs_as_relationship.get(xref.prefix):
            return term.append_relationship(predicate, xref)
        elif xref.prefix in macro_config.treat_xrefs_as_is_a:
            return term.append_parent(xref)
    if xref.prefix in PROVENANCE_PREFIXES:
        return term.append_provenance(xref)
    return term.append_xref(xref)


def _get_subsetdefs(graph: nx.MultiDiGraph, ontology_prefix: str) -> list[tuple[Reference, str]]:
    rv = []
    for subsetdef in graph.get("subsetdef", []):
        left, _, right = subsetdef.partition(" ")
        if not right:
            logger.warning("[%s] subsetdef did not have two parts", ontology_prefix, subsetdef)
            continue
        left_ref = _parse_identifier(left, ontology_prefix=ontology_prefix)
        if left_ref is None:
            logger.warning(
                "[%s] subsetdef identifier could not be parsed", ontology_prefix, subsetdef
            )
            continue
        right = right.strip('"')
        rv.append((left_ref, right))
    return rv


def _clean_graph_ontology(graph, prefix: str) -> None:
    """Update the ontology entry in the graph's metadata, if necessary."""
    if "ontology" not in graph.graph:
        logger.warning('[%s] missing "ontology" key', prefix)
        graph.graph["ontology"] = prefix
    elif not graph.graph["ontology"].isalpha():
        logger.warning(
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
            logger.warning(
                "[%s] had version %s, overriding with %s", ontology_prefix, data_version, version
            )
        return clean_injected_version

    if data_version:
        clean_data_version = cleanup_version(data_version, prefix=ontology_prefix)
        logger.info("[%s] using version %s", ontology_prefix, clean_data_version)
        return clean_data_version

    if date is not None:
        derived_date_version = date.strftime("%Y-%m-%d")
        logger.info(
            "[%s] does not report a version. falling back to date: %s",
            ontology_prefix,
            derived_date_version,
        )
        return derived_date_version

    logger.warning("[%s] does not report a version nor a date", ontology_prefix)
    return None


def _iter_obo_graph(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
    ontology_prefix: str | None = None,
) -> Iterable[tuple[Reference, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in graph.nodes(data=True):
        node = Reference.from_curie_or_uri(
            node, strict=strict, ontology_prefix=ontology_prefix, name=data.get("name")
        )
        if node:
            yield node, data


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
        synonym_typedef_id, name = line.split(" ", 1)
        name = name.strip().strip('"')
        reference = _parse_identifier(
            synonym_typedef_id,
            ontology_prefix=ontology_prefix,
            name=name,
            upgrade=upgrade,
            strict=strict,
        )
        if reference is None:
            logger.warning(
                "[%s] unable to parse synonym typedef ID %s", ontology_prefix, synonym_typedef_id
            )
            continue
        # TODO handle specificity
        yield SynonymTypeDef(reference=reference)


def iterate_graph_typedefs(
    graph: nx.MultiDiGraph,
    *,
    ontology_prefix: str,
    strict: bool = True,
    upgrade: bool,
    macro_config: MacroConfig | None = None,
) -> Iterable[TypeDef]:
    """Get type definitions from an :mod:`obonet` graph."""
    for typedef in graph.graph.get("typedefs", []):
        if "id" in typedef:
            typedef_id = typedef["id"]
        elif "identifier" in typedef:
            typedef_id = typedef["identifier"]
        else:
            raise KeyError("typedef is missing an `id`")

        name = typedef.get("name")
        if name is None:
            logger.debug("[%s] typedef %s is missing a name", ontology_prefix, typedef_id)

        reference = _parse_identifier(
            typedef_id, strict=strict, ontology_prefix=ontology_prefix, name=name, upgrade=upgrade
        )
        if reference is None:
            logger.warning("[%s] unable to parse typedef ID %s", ontology_prefix, typedef_id)
            continue

        yv = TypeDef(reference=reference)

        for xref_curie in typedef.get("xref", []):
            _xref = Reference.from_curie_or_uri(
                xref_curie,
                strict=strict,
                ontology_prefix=ontology_prefix,
                node=reference,
            )
            if not _xref:
                continue
            _handle_xref(
                yv,
                _xref,
                macro_config=macro_config,
            )

        yield yv


def get_definition(
    data, *, node: Reference, ontology_prefix: str | None, strict: bool = True
) -> tuple[None | str, list[Reference]]:
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
    ontology_prefix: str | None,
) -> tuple[None | str, list[Reference]]:
    """Extract the definitions."""
    if not s.startswith('"'):
        logger.warning(f"[{node.curie}] definition does not start with a quote")
        return None, []

    try:
        definition, rest = _quote_split(s)
    except ValueError as e:
        logger.warning("[%s] failed to parse definition quotes: %s", node.curie, str(e))
        return None, []

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning(
            "[%s] missing square brackets in rest of: %s (rest = `%s`)", node.curie, s, rest
        )
        provenance = []
    else:
        provenance = _parse_trailing_ref_list(
            rest, strict=strict, node=node, ontology_prefix=ontology_prefix
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
    strict: bool = True,
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
        rest, strict=strict, node=node, ontology_prefix=ontology_prefix
    )
    annotations = _chomp_axioms(rest, node=node, strict=strict)

    return Synonym(
        name=name,
        specificity=specificity,
        type=synonym_typedef.reference if synonym_typedef else None,
        provenance=provenance,
        annotations=annotations,
    )


#: A counter for errors in parsing provenance
PROVENANCE_COUNTER: Counter[str] = Counter()


def _parse_trailing_ref_list(
    rest: str, *, strict: bool = True, node: Reference, ontology_prefix: str | None
) -> list[Reference]:
    rest = rest.lstrip("[").rstrip("]")  # FIXME this doesn't account for trailing annotations
    rv = []
    for curie in rest.split(","):
        curie = curie.strip()
        if not curie:
            continue
        reference = Reference.from_curie_or_uri(
            curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if reference is None:
            if not PROVENANCE_COUNTER[curie]:
                logger.warning("[%s] could not parse provenance CURIE: %s", node.curie, curie)
            PROVENANCE_COUNTER[curie] += 1
            continue
        rv.append(reference)
    return rv


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

    Example strings:
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


HANDLED_PROPERTY_TYPES = {
    "xsd:string": str,
    "xsd:dateTime": datetime,
}


def iterate_node_properties(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = True,
    ontology_prefix: str,
    upgrade: bool,
) -> Iterable[Annotation]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get("property_value", []):
        if yv := _handle_prop(
            prop_value_type,
            node=node,
            strict=strict,
            ontology_prefix=ontology_prefix,
            upgrade=upgrade,
        ):
            yield yv


#: Keep track of property-value pairs for which the value couldn't be parsed,
#: such as `dc:conformsTo autoimmune:inflammation.yaml` in MONDO
UNHANDLED_PROP_OBJECTS: Counter[tuple[Reference, str]] = Counter()

UNHANDLED_PROPS: Counter[str] = Counter()


def _handle_prop(
    prop_value_type: str,
    *,
    node: Reference,
    strict: bool = True,
    ontology_prefix: str,
    upgrade: bool,
) -> Annotation | None:
    try:
        prop, value_type = prop_value_type.split(" ", 1)
    except ValueError:
        logger.warning("[%s] property_value is missing a space: %s", node.curie, prop_value_type)
        return None

    prop_reference = _get_prop(
        prop, node=node, strict=strict, ontology_prefix=ontology_prefix, upgrade=upgrade
    )
    if prop_reference is None:
        if not UNHANDLED_PROPS[prop]:
            logger.warning("[%s] unparsable property: %s", node.curie, prop)
        UNHANDLED_PROPS[prop] += 1
        return None

    # if the value doesn't start with a quote, we're going to
    # assume that it's a reference
    if not value_type.startswith('"'):
        obj_reference = _parse_identifier(
            value_type, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        if obj_reference is None:
            if not UNHANDLED_PROP_OBJECTS[prop_reference, value_type]:
                logger.warning(
                    "[%s - %s] could not parse object: %s",
                    node.curie,
                    prop_reference.curie,
                    value_type,
                )
            UNHANDLED_PROP_OBJECTS[prop_reference, value_type] += 1
            return None
        return Annotation(prop_reference, obj_reference)

    try:
        value, datatype = value_type.rsplit(" ", 1)  # second entry is the value type
    except ValueError:
        logger.warning(
            "[%s] property missing datatype. defaulting to string - %s", node.curie, prop_value_type
        )
        value = value_type
        datatype = ""

    value = value.strip('"')

    if not datatype:
        return Annotation(prop_reference, OBOLiteral.string(value))

    datatype_reference = Reference.from_curie_or_uri(
        datatype, strict=strict, ontology_prefix=ontology_prefix, node=node
    )
    if datatype_reference is None:
        logger.warning("[%s] had unparsable datatype %s", node.curie, prop_value_type)
        return None
    return Annotation(prop_reference, OBOLiteral(value, datatype_reference))


def _get_prop(
    property_id: str, *, node: Reference, strict: bool, ontology_prefix: str, upgrade: bool
) -> Reference | None:
    for delim in "#/":
        sw = f"http://purl.obolibrary.org/obo/{ontology_prefix}{delim}"
        if property_id.startswith(sw):
            identifier = property_id.removeprefix(sw)
            return default_reference(ontology_prefix, identifier)
    return _parse_identifier(
        property_id, strict=strict, node=node, ontology_prefix=ontology_prefix, upgrade=upgrade
    )


def iterate_node_parents(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = True,
    ontology_prefix: str,
) -> Iterable[Reference]:
    """Extract parents from a :mod:`obonet` node's data."""
    for parent_curie in data.get("is_a", []):
        reference = Reference.from_curie_or_uri(
            parent_curie, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        if reference is None:
            logger.warning("[%s] could not parse parent curie: %s", node.curie, parent_curie)
            continue
        yield reference


def iterate_node_alt_ids(
    data: Mapping[str, Any], *, node: Reference, strict: bool = True, ontology_prefix: str | None
) -> Iterable[Reference]:
    """Extract alternate identifiers from a :mod:`obonet` node's data."""
    for curie in data.get("alt_id", []):
        reference = Reference.from_curie_or_uri(
            curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if reference is not None:
            yield reference


def iterate_node_relationships(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = True,
    ontology_prefix: str,
    upgrade: bool,
) -> Iterable[tuple[Reference, Reference]]:
    """Extract relationships from a :mod:`obonet` node's data."""
    for s in data.get("relationship", []):
        relation_curie, target_curie = s.split(" ")
        relation = _parse_identifier(
            relation_curie,
            strict=strict,
            ontology_prefix=ontology_prefix,
            node=node,
            upgrade=upgrade,
        )
        if relation is None:
            logger.warning("[%s] could not parse relation %s", node.curie, relation_curie)
            continue

        target = Reference.from_curie_or_uri(
            target_curie, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        if target is None:
            logger.warning("[%s] %s could not parse target %s", node.curie, relation, target_curie)
            continue

        yield relation, target


def iterate_node_xrefs(
    *,
    data: Mapping[str, Any],
    strict: bool = True,
    ontology_prefix: str | None,
    node: Reference,
) -> Iterable[Reference]:
    """Extract xrefs from a :mod:`obonet` node's data."""
    for xref in data.get("xref", []):
        xref = xref.strip()

        if curie_has_blacklisted_prefix(xref) or curie_is_blacklisted(xref) or ":" not in xref:
            continue  # sometimes xref to self... weird

        xref = remap_prefix(xref, ontology_prefix=ontology_prefix)

        split_space = " " in xref
        if split_space:
            _xref_split = xref.split(" ", 1)
            if _xref_split[1][0] not in {'"', "("}:
                logger.debug("[%s] Problem with space in xref %s", node.curie, xref)
                continue
            xref = _xref_split[0]

        yv = Reference.from_curie_or_uri(
            xref, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        if yv is not None:
            yield yv
