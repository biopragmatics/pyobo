"""OBO Readers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import bioontologies.relations
import bioontologies.upgrade
import bioregistry
import networkx as nx
from curies import ReferenceTuple
from more_itertools import pairwise
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .constants import DATE_FORMAT, PROVENANCE_PREFIXES
from .identifier_utils import normalize_curie
from .registries import curie_has_blacklisted_prefix, curie_is_blacklisted, remap_prefix
from .struct import (
    Obo,
    Reference,
    Referenced,
    Synonym,
    SynonymSpecificities,
    SynonymSpecificity,
    SynonymTypeDef,
    Term,
    TypeDef,
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


def from_obo_path(
    path: str | Path,
    prefix: str | None = None,
    *,
    strict: bool = True,
    version: str | None = None,
    **kwargs: Any,
) -> Obo:
    """Get the OBO graph from a path."""
    import obonet

    path = Path(path).expanduser().resolve()
    if path.suffix.endswith(".gz"):
        logger.info("[%s] parsing zipped ontology with obonet from %s", prefix or "", path)
        graph = obonet.read_obo(path)
    else:
        logger.info("[%s] parsing with obonet from %s", prefix or "", path)
        with open(path) as file:
            graph = obonet.read_obo(
                tqdm(
                    file,
                    unit_scale=True,
                    desc=f'[{prefix or ""}] parsing obo',
                    disable=None,
                    leave=True,
                )
            )

    if prefix:
        # Make sure the graph is named properly
        _clean_graph_ontology(graph, prefix)

    if not graph.graph.get("name"):
        graph.graph["name"] = bioregistry.get_name(prefix)

    if version:
        data_version = graph.graph.get("data-version")
        if data_version is None:
            graph.graph["data-version"] = version

    # Convert to an Obo instance and return
    return from_obonet(graph, strict=strict, **kwargs)


def from_obonet(graph: nx.MultiDiGraph, *, strict: bool = True) -> Obo:
    """Get all of the terms from a OBO graph."""
    ontology_prefix_raw = graph.graph["ontology"]
    ontology_prefix = bioregistry.normalize_prefix(ontology_prefix_raw)  # probably always okay
    if ontology_prefix is None:
        raise ValueError(f"unknown prefix: {ontology_prefix_raw}")

    date = _get_date(graph=graph, ontology=ontology_prefix)
    name = _get_name(graph=graph, ontology=ontology_prefix)

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
            logger.info("[%s] does not report a data version nor a date", ontology_prefix)
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
        logger.warning(f"[{ontology_prefix}] has a nonstandard data version: {data_version}")

    #: CURIEs to typedefs
    typedefs: dict[ReferenceTuple, TypeDef] = {
        typedef.pair: typedef
        for typedef in iterate_graph_typedefs(graph, strict=strict, ontology_prefix=ontology_prefix)
    }

    synonym_typedefs: dict[str, SynonymTypeDef] = {
        synonym_typedef.curie: synonym_typedef
        for synonym_typedef in iterate_graph_synonym_typedefs(
            graph, ontology_prefix=ontology_prefix, strict=strict
        )
    }

    missing_typedefs = set()
    terms = []
    n_alt_ids, n_parents, n_synonyms, n_relations = 0, 0, 0, 0
    n_properties, n_xrefs, n_nodes = 0, 0, 0
    for node, data in _iter_obo_graph(graph=graph, strict=strict, ontology_prefix=ontology_prefix):
        with logging_redirect_tqdm():
            n_nodes += 1

            # Skip nodes that dont have the same prefix as the ontology
            if node.prefix != ontology_prefix or not data:
                continue

            xrefs, provenance = [], []
            for node_xref in iterate_node_xrefs(
                node=node, data=data, strict=strict, ontology_prefix=ontology_prefix
            ):
                if node_xref.prefix in PROVENANCE_PREFIXES:
                    provenance.append(node_xref)
                else:
                    xrefs.append(node_xref)
            n_xrefs += len(xrefs)

            definition, definition_references = get_definition(node=node, data=data)
            if definition_references:
                provenance.extend(definition_references)

            alt_ids = list(
                iterate_node_alt_ids(
                    node=node, data=data, strict=strict, ontology_prefix=ontology_prefix
                )
            )
            n_alt_ids += len(alt_ids)

            parents = list(
                iterate_node_parents(
                    node=node, data=data, strict=strict, ontology_prefix=ontology_prefix
                )
            )
            n_parents += len(parents)

            synonyms = list(
                iterate_node_synonyms(
                    node=node,
                    data=data,
                    synonym_typedefs=synonym_typedefs,
                    strict=strict,
                    ontology_prefix=ontology_prefix,
                )
            )
            n_synonyms += len(synonyms)

            term = Term(
                reference=node,
                definition=definition,
                parents=parents,
                synonyms=synonyms,
                xrefs=xrefs,
                provenance=provenance,
                alt_ids=alt_ids,
            )

            for relation, target in iterate_node_relationships(
                data=data, node=node, strict=strict, ontology_prefix=ontology_prefix
            ):
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
                term.append_relationship(typedef, target)

            for prop, value in iterate_node_properties(data, term=term):
                n_properties += 1
                _append_property(term, prop, value, strict=strict, ontology_prefix=ontology_prefix)

            terms.append(term)

    logger.info(
        f"[{ontology_prefix}] got {n_nodes:,} references, {len(typedefs):,} typedefs, {len(terms):,} terms,"
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


UNPARSED_IRIS: set[str] = set()


def _append_property(
    term: Term,
    prop: str | Reference | Referenced,
    value: str | Reference | Referenced,
    *,
    strict: bool,
    ontology_prefix: str,
) -> Term:
    """Append a property."""
    if isinstance(prop, str):
        # TODO do some relation upgrading here too!
        if prop.startswith("http://purl.obolibrary.org/obo/"):
            prop = Reference(
                prefix="obo", identifier=prop.removeprefix("http://purl.obolibrary.org/obo/")
            )
        elif prop.startswith("http"):
            # TODO upstream this into an omni-parser for references?
            _pref, _id = bioregistry.parse_iri(prop)
            if _pref and _id:
                prop = Reference(prefix=_pref, identifier=_id)
            else:
                logger.warning(f"[{term.curie}] unable to handle property: {prop}")
                return term
        else:
            _tmp_prop = _handle_relation_curie(
                prop,
                strict=strict,
                node=term.reference,
                ontology_prefix=ontology_prefix,
            )
            if _tmp_prop is None:
                logger.warning(f"[{term.curie}] could not parse property: {prop}")
                return term
            prop = _tmp_prop

    if not isinstance(value, str):
        return term.annotate_object(prop, value)

    if value.startswith("http"):
        _pref, _id = bioregistry.parse_iri(value)
        if _pref and _id:
            return term.annotate_object(prop, Reference(prefix=_pref, identifier=_id))
        else:
            if value not in UNPARSED_IRIS:
                logger.warning(f"[{term.curie}] could not parse target IRI: {value}")
                UNPARSED_IRIS.add(value)
            return term

    if len(value) > 8 and value[:4].isnumeric() and value[4] == "-" and value[5:7].isnumeric():
        if len(value) == 10:  # it's YYYY-MM-DD
            return term.annotate_literal(
                prop, value, datatype=Reference(prefix="xsd", identifier="date")
            )
        # assume it's a full datetime
        return term.annotate_literal(
            prop, value, datatype=Reference(prefix="xsd", identifier="dateTime")
        )

    # assume if there's a string, then it's not a CURIE
    if " " in value:
        return term.annotate_literal(prop, value)

    if ":" in value:
        xx = Reference.from_curie(value, strict=strict)
        if xx is None:
            logger.warning(f"[{term.curie}] {prop.curie} could not parse target curie: {value}")
            return term
        return term.annotate_object(prop, xx)

    return term.annotate_literal(prop, value)


def _clean_graph_ontology(graph, prefix: str) -> None:
    """Update the ontology entry in the graph's metadata, if necessary."""
    ontology = graph.graph.get("ontology")
    if ontology is None:
        logger.debug('[%s] missing "ontology" key', prefix)
        graph.graph["ontology"] = prefix
    elif not ontology.isalpha():
        logger.debug(
            "[%s] ontology key `%s` has a strange format. replacing with prefix",
            prefix,
            ontology,
        )
        graph.graph["ontology"] = prefix


def _iter_obo_graph(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
    ontology_prefix: str,
    use_tqdm: bool = True,
) -> Iterable[tuple[Reference, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for curie, data in tqdm(
        graph.nodes(data=True),
        disable=not use_tqdm,
        unit="node",
        unit_scale=True,
        leave=True,
        desc=f"[{ontology_prefix}] processing graph",
    ):
        # TODO add standardization into Reference.from_curie?
        prefix, identifier = normalize_curie(curie, strict=strict, ontology=ontology_prefix)
        if prefix is None or identifier is None:
            logger.warning("[%s] could not parse node curie: %s", ontology_prefix, curie)
            continue
        identifier = bioregistry.standardize_identifier(prefix, identifier)
        reference = Reference(prefix=prefix, identifier=identifier, name=data.get("name"))
        yield reference, data


def _get_date(graph, ontology: str) -> datetime | None:
    try:
        rv = datetime.strptime(graph.graph["date"], DATE_FORMAT)
    except KeyError:
        logger.info("[%s] does not report a date", ontology)
        return None
    except ValueError:
        logger.info("[%s] reports a date that can't be parsed: %s", ontology, graph.graph["date"])
        return None
    else:
        return rv


def _get_name(graph, ontology: str) -> str:
    try:
        rv = graph.graph["name"]
    except KeyError:
        logger.info("[%s] does not report a name", ontology)
        rv = ontology
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
                logger.warning("[%s] issue parsing synoynm typedef: %s", ontology_prefix, s)
                continue

        yield SynonymTypeDef(reference=reference)


def iterate_graph_typedefs(
    graph: nx.MultiDiGraph,
    *,
    strict: bool = True,
    ontology_prefix: str,
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
            logger.info("[%s] typedef %s is missing a name", ontology_prefix, curie)

        reference = _handle_relation_curie(curie, strict=strict, ontology_prefix=ontology_prefix)
        if reference is None:
            logger.warning("[%s] unable to parse typedef CURIE %s", ontology_prefix, curie)
            continue

        xrefs = []
        for curie in typedef.get("xref", []):
            _xref = Reference.from_curie(curie, strict=strict)
            if _xref:
                xrefs.append(_xref)
        yield TypeDef(reference=reference, xrefs=xrefs)


def _handle_relation_curie(
    curie: str,
    *,
    strict: bool = True,
    name: str | None = None,
    ontology_prefix: str,
    node: Reference | None = None,
) -> Reference | None:
    if curie in RELATION_REMAPPINGS:
        prefix, identifier = RELATION_REMAPPINGS[curie]
        return Reference(prefix=prefix, identifier=identifier)

    if curie.startswith("http"):
        _pref, _id = bioregistry.parse_iri(curie)
        if not _pref or not _id:
            logger.warning("[%s] unable to contract URI %s", ontology_prefix, curie)
            return None
        return Reference(prefix=_pref, identifier=_id)
    elif ":" in curie:
        return Reference.from_curie(curie, name=name, strict=strict, reference=node)
    elif xx := bioontologies.upgrade.upgrade(curie):
        logger.debug(f"upgraded {curie} to {xx}")
        return Reference(prefix=xx.prefix, identifier=xx.identifier)
    elif xx := _ground_rel_helper(curie):
        logger.debug(f"grounded {curie} to {xx}")
        return xx
    elif " " in curie:
        logger.warning("[%s] invalid typedef CURIE %s", ontology_prefix, curie)
        return None
    else:
        reference = _default_reference(ontology_prefix, curie)
        logger.info(
            "[%s] massaging unqualified curie `%s` into %s", ontology_prefix, curie, reference.curie
        )
        return reference


def _parse_object_curie(
    curie: str, *, strict: bool = True, node: Reference, ontology_prefix: str
) -> Reference | None:
    if curie.startswith("http"):
        _pref, _id = bioregistry.parse_iri(curie)
        if not _pref or not _id:
            logger.warning("[%s] unable to contract URI %s", node.prefix, curie)
            return None
        return Reference(prefix=_pref, identifier=_id)

    if xx := bioontologies.upgrade.upgrade(curie):
        logger.debug(f"upgraded {curie} to {xx}")
        return Reference(prefix=xx.prefix, identifier=xx.identifier)

    if ":" not in curie:
        reference = _default_reference(ontology_prefix, curie)
        logger.info(
            "[%s] massaging unqualified curie `%s` into %s", node.prefix, curie, reference.curie
        )
        return reference

    return Reference.from_curie(curie, strict=strict, reference=node)


def _ground_rel_helper(curie) -> Reference | None:
    a, b = bioontologies.relations.ground_relation(curie)
    if a is None or b is None:
        return None
    return Reference(prefix=a, identifier=b)


def get_definition(*, node: Reference, data) -> tuple[None, None] | tuple[str, list[Reference]]:
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
        raise ValueError("definition does not start with a quote")

    try:
        definition, rest = _quote_split(s)
    except ValueError:
        logger.warning("[%s] could not parse definition: %s", node.curie, s)
        return None, None

    if not rest.startswith("[") or not rest.endswith("]"):
        logger.warning("[%s] problem with definition: %s", node.curie, s)
        provenance = []
    else:
        provenance = _parse_trailing_ref_list(rest, strict=strict)
    return definition, provenance


def _get_first_nonquoted(s: str) -> int | None:
    for i, (a, b) in enumerate(pairwise(s), start=1):
        if b == '"' and a != "\\":
            return i
    return None


def _quote_split(s: str) -> tuple[str, str]:
    # TODO test: `The X!Tandem expectation value.`
    s = s.lstrip('"')
    i = _get_first_nonquoted(s)
    if i is None:
        raise ValueError
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
    ontology_prefix: str,
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

    provenance = _parse_trailing_ref_list(rest, strict=strict)
    return Synonym(
        name=name,
        specificity=specificity or "EXACT",
        type=stype or DEFAULT_SYNONYM_TYPE,
        provenance=provenance,
    )


def _parse_trailing_ref_list(rest, *, strict: bool = True):
    rest = rest.lstrip("[").rstrip("]")
    return [
        Reference.from_curie(curie.strip(), strict=strict)
        for curie in rest.split(",")
        if curie.strip()
    ]


def iterate_node_synonyms(
    *,
    node: Reference,
    data: Mapping[str, Any],
    synonym_typedefs: Mapping[str, SynonymTypeDef],
    strict: bool = False,
    ontology_prefix: str,
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
            s, synonym_typedefs, node=node, strict=strict, ontology_prefix=ontology_prefix
        )
        if s is not None:
            yield s


def iterate_node_properties(
    data: Mapping[str, Any], *, property_prefix: str | None = None, term=None
) -> Iterable[tuple[str, str]]:
    """Extract properties from a :mod:`obonet` node's data."""
    for prop_value_type in data.get("property_value", []):
        try:
            prop, value_type = prop_value_type.split(" ", 1)
        except ValueError:
            logger.warning("malformed property: %s on %s", prop_value_type, term and term.curie)
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
    strict: bool = True,
    node: Reference,
    ontology_prefix: str,
) -> Iterable[Reference]:
    """Extract parents from a :mod:`obonet` node's data."""
    for parent_curie in data.get("is_a", []):
        parent_reference = _parse_object_curie(
            parent_curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if parent_reference is None:
            logger.warning("[%s] could not parse parent curie: %s", node.curie, parent_curie)
            continue
        yield parent_reference


def iterate_node_alt_ids(
    data: Mapping[str, Any],
    *,
    strict: bool = True,
    node: Reference,
    ontology_prefix: str,
) -> Iterable[Reference]:
    """Extract alternate identifiers from a :mod:`obonet` node's data."""
    for alt_curie in data.get("alt_id", []):
        alt_reference = _parse_object_curie(
            alt_curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if alt_reference is None:
            logger.warning("[%s] could not parse alt curie: %s", node.curie, alt_curie)
            continue
        yield alt_reference


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
        relation = _handle_relation_curie(
            relation_curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if relation is None:
            logger.warning("[%s] could not parse relation predicate %s", node.curie, relation_curie)
            continue

        target = _parse_object_curie(
            target_curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if target is None:
            logger.warning("[%s] %s could not parse target: %s", node.curie, relation, target_curie)
            continue

        yield relation, target


def _default_reference(ontology_prefix: str, s: str) -> Reference:
    return Reference(prefix="obo", identifier=f"{ontology_prefix}#{s}")


def iterate_node_xrefs(
    *, data: Mapping[str, Any], strict: bool = True, node: Reference, ontology_prefix: str
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
                logger.debug("[%s] Problem with space in xref %s", node.prefix, xref)
                continue
            xref = _xref_split[0]

        yv = Reference.from_curie(xref, strict=strict, reference=node)
        if yv is not None:
            yield yv
