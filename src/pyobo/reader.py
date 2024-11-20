"""OBO Readers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import bioontologies.upgrade
import bioregistry
import networkx as nx
from curies import ReferenceTuple
from more_itertools import pairwise
from tqdm.auto import tqdm

from .constants import DATE_FORMAT, PROVENANCE_PREFIXES
from .identifier_utils import normalize_curie
from .registries import curie_has_blacklisted_prefix, curie_is_blacklisted, remap_prefix
from .struct import (
    Obo,
    Reference,
    Synonym,
    SynonymSpecificities,
    SynonymSpecificity,
    SynonymTypeDef,
    Term,
    TypeDef,
    default_reference,
    make_ad_hoc_ontology,
)
from .struct.struct import DEFAULT_SYNONYM_TYPE
from .struct.typedef import default_typedefs
from .utils.misc import cleanup_version

__all__ = [
    "from_obo_path",
    "from_obonet",
]

logger = logging.getLogger(__name__)

RELATION_REMAPPINGS: Mapping[str, ReferenceTuple] = bioontologies.upgrade.load()


def from_obo_path(path: str | Path, prefix: str | None = None, *, strict: bool = True) -> Obo:
    """Get the OBO graph from a path."""
    import obonet

    logger.info("[%s] parsing with obonet from %s", prefix or "", path)
    with open(path) as file:
        graph = obonet.read_obo(
            tqdm(
                file,
                unit_scale=True,
                desc=f'[{prefix or ""}] parsing obo',
                disable=None,
                leave=False,
            )
        )

    if prefix:
        # Make sure the graph is named properly
        _clean_graph_ontology(graph, prefix)

    # Convert to an Obo instance and return
    return from_obonet(graph, strict=strict)


def from_obonet(graph: nx.MultiDiGraph, *, strict: bool = True) -> Obo:
    """Get all of the terms from a OBO graph."""
    ontology_prefix_raw = graph.graph["ontology"]
    ontology_prefix = bioregistry.normalize_prefix(ontology_prefix_raw)  # probably always okay
    if ontology_prefix is None:
        raise ValueError(f"unknown prefix: {ontology_prefix_raw}")
    logger.info("[%s] extracting OBO using obonet", ontology_prefix)

    date = _get_date(graph=graph, ontology_prefix=ontology_prefix)
    name = _get_name(graph=graph, ontology_prefix=ontology_prefix)

    data_version = graph.graph.get("data-version")
    if not data_version:
        if date is not None:
            data_version = date.strftime("%Y-%m-%d")
            logger.info(
                "[%s] does not report a version. falling back to date: %s",
                ontology_prefix,
                data_version,
            )
        else:
            logger.warning("[%s] does not report a version nor a date", ontology_prefix)
    else:
        data_version = cleanup_version(data_version=data_version, prefix=ontology_prefix)
        if data_version is not None:
            logger.info("[%s] using version %s", ontology_prefix, data_version)
        elif date is not None:
            logger.info(
                "[%s] unrecognized version format, falling back to date: %s",
                ontology_prefix,
                data_version,
            )
            data_version = date.strftime("%Y-%m-%d")
        else:
            logger.warning(
                "[%s] UNRECOGNIZED VERSION FORMAT AND MISSING DATE: %s",
                ontology_prefix,
                data_version,
            )

    if data_version and "/" in data_version:
        raise ValueError(
            f"[{ontology_prefix}] will not accept slash in data version: {data_version}"
        )

    #: Parsed CURIEs to references (even external ones)
    reference_it = (
        Reference(
            prefix=prefix,
            identifier=bioregistry.standardize_identifier(prefix, identifier),
            # if name isn't available, it means its external to this ontology
            name=data.get("name"),
        )
        for prefix, identifier, data in _iter_obo_graph(graph=graph, strict=strict)
    )
    references: Mapping[ReferenceTuple, Reference] = {
        reference.pair: reference for reference in reference_it
    }

    #: CURIEs to typedefs
    typedefs: Mapping[ReferenceTuple, TypeDef] = {
        typedef.pair: typedef
        for typedef in iterate_graph_typedefs(graph, ontology_prefix=ontology_prefix)
    }

    synonym_typedefs: Mapping[str, SynonymTypeDef] = {
        synonym_typedef.curie: synonym_typedef
        for synonym_typedef in iterate_graph_synonym_typedefs(
            graph, ontology_prefix=ontology_prefix
        )
    }

    missing_typedefs: set[ReferenceTuple] = set()
    terms = []
    n_alt_ids, n_parents, n_synonyms, n_relations, n_properties, n_xrefs = 0, 0, 0, 0, 0, 0
    for prefix, identifier, data in _iter_obo_graph(graph=graph, strict=strict):
        if prefix != ontology_prefix or not data:
            continue

        identifier = bioregistry.standardize_identifier(prefix, identifier)
        reference = references[ReferenceTuple(ontology_prefix, identifier)]

        node_xrefs = list(iterate_node_xrefs(prefix=prefix, data=data, strict=strict))
        xrefs, provenance = [], []
        for node_xref in node_xrefs:
            if node_xref.prefix in PROVENANCE_PREFIXES:
                provenance.append(node_xref)
            else:
                xrefs.append(node_xref)
        n_xrefs += len(xrefs)

        definition, definition_references = get_definition(data, node=reference)
        if definition_references:
            provenance.extend(definition_references)

        alt_ids = list(iterate_node_alt_ids(data, strict=strict))
        n_alt_ids += len(alt_ids)

        parents = list(iterate_node_parents(data, node=reference, strict=strict))
        n_parents += len(parents)

        synonyms = list(
            iterate_node_synonyms(data, synonym_typedefs, node=reference, strict=strict)
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

        relations_references = list(
            iterate_node_relationships(
                data,
                node=reference,
                strict=strict,
                ontology_prefix=ontology_prefix,
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
        for prop, value in iterate_node_properties(data, term=term):
            n_properties += 1
            term.append_property(prop, value)
        terms.append(term)

    logger.info(
        f"[{ontology_prefix}] got {len(references):,} references, {len(typedefs):,} typedefs, {len(terms):,} terms,"
        f" {n_alt_ids:,} alt ids, {n_parents:,} parents, {n_synonyms:,} synonyms, {n_xrefs:,} xrefs,"
        f" {n_relations:,} relations, and {n_properties:,} properties",
    )

    return make_ad_hoc_ontology(
        _ontology=ontology_prefix,
        _name=name,
        _auto_generated_by=graph.graph.get("auto-generated-by"),
        _format_version=graph.graph.get("format-version"),
        _typedefs=list(typedefs.values()),
        _synonym_typedefs=list(synonym_typedefs.values()),
        _date=date,
        _data_version=data_version,
        terms=terms,
    )


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


def _iter_obo_graph(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
) -> Iterable[tuple[str, str, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in graph.nodes(data=True):
        prefix, identifier = normalize_curie(node, strict=strict)
        if prefix is None or identifier is None:
            continue
        yield prefix, identifier, data


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
    graph: nx.MultiDiGraph, *, ontology_prefix: str, strict: bool = False
) -> Iterable[SynonymTypeDef]:
    """Get synonym type definitions from an :mod:`obonet` graph."""
    for s in graph.graph.get("synonymtypedef", []):
        sid, name = s.split(" ", 1)
        name = name.strip().strip('"')
        if sid.startswith("http://") or sid.startswith("https://"):
            reference = Reference.from_iri(sid, name=name)
        elif ":" not in sid:  # assume it's ad-hoc
            reference = Reference(prefix=ontology_prefix, identifier=sid, name=name)
        else:  # assume it's a curie
            reference = Reference.from_curie(sid, name=name, strict=strict)

        if reference is None:
            if strict:
                raise ValueError(f"Could not parse {sid}")
            else:
                continue

        yield SynonymTypeDef(reference=reference)


def iterate_graph_typedefs(
    graph: nx.MultiDiGraph, *, ontology_prefix: str, strict: bool = True
) -> Iterable[TypeDef]:
    """Get type definitions from an :mod:`obonet` graph."""
    for typedef in graph.graph.get("typedefs", []):
        if "id" in typedef:
            curie = typedef["id"]
        elif "identifier" in typedef:
            curie = typedef["identifier"]
        else:
            raise KeyError("typedef is missing an `id`")

        name = typedef.get("name")
        if name is None:
            logger.debug("[%s] typedef %s is missing a name", graph.graph["ontology"], curie)

        if ":" in curie:
            reference = Reference.from_curie(curie, name=name, strict=strict)
        else:
            reference = default_reference(ontology_prefix, curie, name=name)
        if reference is None:
            logger.warning("[%s] unable to parse typedef CURIE %s", graph.graph["ontology"], curie)
            continue

        xrefs = []
        for curie in typedef.get("xref", []):
            _xref = Reference.from_curie(curie, strict=strict)
            if _xref:
                xrefs.append(_xref)
        yield TypeDef(reference=reference, xrefs=xrefs)


def get_definition(data, *, node: Reference) -> tuple[None, None] | tuple[str, list[Reference]]:
    """Extract the definition from the data."""
    definition = data.get("def")  # it's allowed not to have a definition
    if not definition:
        return None, None
    return _extract_definition(definition, node=node)


def _extract_definition(
    s: str,
    *,
    node: Reference,
    strict: bool = False,
) -> tuple[None, None] | tuple[str, list[Reference]]:
    """Extract the definitions."""
    if not s.startswith('"'):
        raise ValueError(f"[{node.curie}] definition does not start with a quote")

    try:
        definition, rest = _quote_split(s)
    except ValueError as e:
        logger.warning("[%s] failed to parse definition quotes: %s", node.curie, str(e))
        return None, None

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning("[%s] problem with definition: %s", node.curie, s)
        provenance = []
    else:
        provenance = _parse_trailing_ref_list(rest, strict=strict, node=node)
    return definition, provenance


def _get_first_nonquoted(s: str) -> int | None:
    for i, (a, b) in enumerate(pairwise(s), start=1):
        if b == '"' and a != "\\":
            return i
    return None


def _quote_split(s: str) -> tuple[str, str]:
    s = s.lstrip('"')
    i = _get_first_nonquoted(s)
    if i is None:
        raise ValueError(f"no closing quote found in `{s}`")
    return _clean_definition(s[:i].strip()), s[i + 1 :].strip()


def _clean_definition(s: str) -> str:
    # if '\t' in s:
    #     logger.warning('has tab')
    return s.replace('\\"', '"').replace("\n", " ").replace("\t", " ").replace(r"\d", "")


def _extract_synonym(
    s: str,
    synonym_typedefs: Mapping[str, SynonymTypeDef],
    *,
    node: Reference,
    strict: bool = True,
) -> Synonym | None:
    # TODO check if the synonym is written like a CURIE... it shouldn't but I've seen it happen
    try:
        name, rest = _quote_split(s)
    except ValueError:
        logger.warning("[%s] invalid synonym: %s", node.curie, s)
        return None

    specificity: SynonymSpecificity | None = None
    for _specificity in SynonymSpecificities:
        if rest.startswith(_specificity):
            specificity = _specificity
            rest = rest[len(_specificity) :].strip()
            break

    stype: SynonymTypeDef | None = None
    for _stype in synonym_typedefs.values():
        # Since there aren't a lot of carefully defined synonym definitions, it
        # can appear as a string or curie. Therefore, we might see temporary prefixes
        # get added, so we should check against full curies as well as local unique
        # identifiers
        if rest.startswith(_stype.curie):
            rest = rest[len(_stype.curie) :].strip()
            stype = _stype
            break
        elif rest.startswith(_stype.preferred_curie):
            rest = rest[len(_stype.preferred_curie) :].strip()
            stype = _stype
            break
        elif rest.startswith(_stype.identifier):
            rest = rest[len(_stype.identifier) :].strip()
            stype = _stype
            break

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning("[%s] problem with synonym: %s", node.curie, s)
        return None

    provenance = _parse_trailing_ref_list(rest, strict=strict, node=node)
    return Synonym(
        name=name,
        specificity=specificity or "EXACT",
        type=stype or DEFAULT_SYNONYM_TYPE,
        provenance=provenance,
    )


def _parse_trailing_ref_list(rest, *, strict: bool = True, node: Reference):
    rest = rest.lstrip("[").rstrip("]")
    return [
        Reference.from_curie(curie.strip(), strict=strict, node=node)
        for curie in rest.split(",")
        if curie.strip()
    ]


def iterate_node_synonyms(
    data: Mapping[str, Any],
    synonym_typedefs: Mapping[str, SynonymTypeDef],
    *,
    node: Reference,
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
        s = _extract_synonym(s, synonym_typedefs, node=node, strict=strict)
        if s is not None:
            yield s


HANDLED_PROPERTY_TYPES = {
    "xsd:string": str,
    "xsd:dateTime": datetime,
}


def iterate_node_properties(
    data: Mapping[str, Any], *, property_prefix: str | None = None, term=None
) -> Iterable[tuple[str, str]]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get("property_value", []):
        try:
            prop, value_type = prop_value_type.split(" ", 1)
        except ValueError:
            logger.info("malformed property: %s on %s", prop_value_type, term and term.curie)
            continue
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
    node: Reference,
    strict: bool = True,
) -> Iterable[Reference]:
    """Extract parents from a :mod:`obonet` node's data."""
    for parent_curie in data.get("is_a", []):
        reference = Reference.from_curie(parent_curie, strict=strict)
        if reference is None:
            logger.warning("[%s] could not parse parent curie: %s", node.curie, parent_curie)
            continue
        yield reference


def iterate_node_alt_ids(data: Mapping[str, Any], *, strict: bool = True) -> Iterable[Reference]:
    """Extract alternate identifiers from a :mod:`obonet` node's data."""
    for curie in data.get("alt_id", []):
        reference = Reference.from_curie(curie, strict=strict)
        if reference is not None:
            yield reference


def iterate_node_relationships(
    data: Mapping[str, Any],
    *,
    node: Reference,
    strict: bool = True,
    ontology_prefix: str,
) -> Iterable[tuple[Reference, Reference]]:
    """Extract relationships from a :mod:`obonet` node's data."""
    for s in data.get("relationship", []):
        relation_curie, target_curie = s.split(" ")
        relation_prefix: str | None
        relation_identifier: str | None
        if relation_curie in RELATION_REMAPPINGS:
            relation_prefix, relation_identifier = RELATION_REMAPPINGS[relation_curie]
        else:
            relation_prefix, relation_identifier = normalize_curie(relation_curie, strict=strict)
        if relation_prefix is not None and relation_identifier is not None:
            relation = Reference(prefix=relation_prefix, identifier=relation_identifier)
        else:
            relation = default_reference(ontology_prefix, relation_curie)
            logger.debug(
                "unhandled relation: %s. Parsing as default relation: %s",
                relation_curie,
                relation.curie,
            )

        # TODO replace with omni-parser from :mod:`curies`
        target = Reference.from_curie(target_curie, strict=strict)
        if target is None:
            logger.warning("[%s] %s could not parse target %s", node.curie, relation, target_curie)
            continue

        yield relation, target


def iterate_node_xrefs(
    *, prefix: str, data: Mapping[str, Any], strict: bool = True
) -> Iterable[Reference]:
    """Extract xrefs from a :mod:`obonet` node's data."""
    for xref in data.get("xref", []):
        xref = xref.strip()

        if curie_has_blacklisted_prefix(xref) or curie_is_blacklisted(xref) or ":" not in xref:
            continue  # sometimes xref to self... weird

        xref = remap_prefix(xref)

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
