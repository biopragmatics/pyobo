"""Exports to OBO Graph JSON."""

import tempfile
from pathlib import Path

import bioregistry
import curies
import obographs as og
from curies import Converter, ReferenceTuple
from curies import vocabulary as v

from pyobo.identifier_utils.api import get_converter
from pyobo.struct import Obo, OBOLiteral, Stanza, Term, TypeDef
from pyobo.struct import typedef as tdv
from pyobo.utils.io import safe_open

__all__ = [
    "to_obograph",
    "to_parsed_obograph",
    "write_obograph",
]


def write_obograph(obo: Obo, path: str | Path, *, converter: Converter | None = None) -> None:
    """Write an ontology to a file as OBO Graph JSON."""
    path = Path(path).expanduser().resolve()
    raw_graph = to_obograph(obo, converter=converter)
    with safe_open(path, read=False) as file:
        file.write(raw_graph.model_dump_json(indent=2, exclude_none=True, exclude_unset=True))


def to_parsed_obograph_oracle(
    obo: Obo, *, converter: Converter | None = None
) -> og.StandardizedGraphDocument:
    """Serialize to OBO, convert to OBO Graph JSON with ROBOT, load, then parse."""
    import bioontologies.robot

    if converter is None:
        converter = get_converter()

    with tempfile.TemporaryDirectory() as directory:
        stub = Path(directory).joinpath("test")
        obo_path = stub.with_suffix(".obo")
        obograph_path = stub.with_suffix(".json")
        obo.write_obo(obo_path)
        bioontologies.robot.convert(input_path=obo_path, output_path=obograph_path)
        raw = og.read(obograph_path, squeeze=False)
    rv = raw.standardize(converter)
    for graph in rv.graphs:
        if graph.meta and graph.meta.properties:
            graph.meta.properties = [
                p
                for p in graph.meta.properties
                if p.predicate.pair
                != ReferenceTuple(prefix="oboinowl", identifier="hasOBOFormatVersion")
            ] or None
    return rv


def to_obograph(obo: Obo, *, converter: Converter | None = None) -> og.GraphDocument:
    """Convert an ontology to a OBO Graph JSON document."""
    if converter is None:
        converter = get_converter()
    return to_parsed_obograph(obo).to_raw(converter)


def to_parsed_obograph(obo: Obo) -> og.StandardizedGraphDocument:
    """Convert an ontology to a processed OBO Graph JSON document."""
    return og.StandardizedGraphDocument(graphs=[_to_parsed_graph(obo)])


def _to_parsed_graph(obo: Obo) -> og.StandardizedGraph:
    return og.StandardizedGraph(
        id=f"http://purl.obolibrary.org/obo/{obo.ontology}.owl",
        meta=_get_meta(obo),
        nodes=_get_nodes(obo),
        edges=_get_edges(obo),
        equivalent_node_sets=_get_equivalent_node_sets(obo),
        property_chain_axioms=_get_property_chain_axioms(obo),
        domain_range_axioms=_get_domain_ranges(obo),
        logical_definition_axioms=_get_logical_definition_axioms(obo),
    )


def _get_logical_definition_axioms(obo: Obo) -> list[og.StandardizedLogicalDefinition]:
    rv: list[og.StandardizedLogicalDefinition] = []
    # TODO
    return rv


def _get_domain_ranges(obo: Obo) -> list[og.StandardizedDomainRangeAxiom]:
    rv = []
    for typedef in obo.typedefs or []:
        if typedef.domain or typedef.range:
            rv.append(
                og.StandardizedDomainRangeAxiom(
                    predicate=typedef.reference,
                    domains=[typedef.domain] if typedef.domain else [],
                    ranges=[typedef.range] if typedef.range else [],
                )
            )
    return rv


def _get_equivalent_node_sets(obo: Obo) -> list[og.StandardizedEquivalentNodeSet]:
    rv = []
    for node in obo:
        for e in node.equivalent_to:
            rv.append(og.StandardizedEquivalentNodeSet(node=node.reference, equivalents=[e]))
    return rv


def _get_property_chain_axioms(obo: Obo) -> list[og.StandardizedPropertyChainAxiom]:
    rv = []
    for typedef in obo.typedefs or []:
        for chain in typedef.holds_over_chain:
            rv.append(
                og.StandardizedPropertyChainAxiom(
                    predicate=typedef.reference,
                    chain=chain,
                )
            )
        # TODO typedef.equivalent_to_chain
    return rv


def _get_meta(obo: Obo) -> og.StandardizedMeta | None:
    properties = []

    if description := bioregistry.get_description(obo.ontology):
        properties.append(
            og.StandardizedProperty(
                predicate=v.has_description,
                value=description,
            )
        )

        for root_term in obo.root_terms or []:
            properties.append(
                og.StandardizedProperty(
                    predicate=v.has_ontology_root_term,
                    value=root_term,
                )
            )

    if license_spdx_id := bioregistry.get_license(obo.ontology):
        properties.append(
            og.StandardizedProperty(
                predicate=v.has_license,
                value=license_spdx_id,
            )
        )

    if obo.name:
        properties.append(
            og.StandardizedProperty(
                predicate=v.has_title,
                value=obo.name,
            )
        )

    for p in obo.property_values or []:
        properties.append(
            og.StandardizedProperty(
                predicate=p.predicate,
                value=p.value.value if isinstance(p.value, OBOLiteral) else p.value,
            )
        )

    if obo.data_version:
        version_iri = (
            f"http://purl.obolibrary.org/obo/{obo.ontology}/{obo.data_version}/{obo.ontology}.owl"
        )
    else:
        version_iri = None

    # comments don't make the round trip
    subsets = [r for r, _ in obo.subsetdefs or []] or None

    if not properties and not version_iri and not subsets:
        return None

    return og.StandardizedMeta(
        properties=properties or None,
        version_iri=version_iri,
        subsets=subsets,
    )


def _get_nodes(obo: Obo) -> list[og.StandardizedNode]:
    rv = []
    for term in obo:
        rv.append(_get_class_node(term))
    for typedef in _get_typedefs(obo):
        rv.append(_get_typedef_node(typedef))
    return rv


def _get_typedefs(obo: Obo) -> set[TypeDef]:
    rv = set(obo.typedefs or [])
    if obo.auto_generated_by:
        rv.add(tdv.obo_autogenerated_by)
    return rv


def _get_definition(stanza: Stanza) -> og.StandardizedDefinition | None:
    if not stanza.definition:
        return None
    return og.StandardizedDefinition(
        value=stanza.definition,
        xrefs=[p for p in stanza.provenance if isinstance(p, curies.Reference)],
    )


def _get_synonyms(stanza: Stanza) -> list[og.StandardizedSynonym] | None:
    return [
        og.StandardizedSynonym(
            text=synonym.name,
            predicate=v.synonym_scopes[synonym.specificity]
            if synonym.specificity is not None
            else v.has_related_synonym,
            type=synonym.type,
            xrefs=[p for p in synonym.provenance if isinstance(p, curies.Reference)],
        )
        for synonym in stanza.synonyms
    ] or None


def _get_properties(term: Stanza) -> list[og.StandardizedProperty] | None:
    properties = []
    for predicate, obj in term.iterate_object_properties():
        properties.append(
            og.StandardizedProperty(
                predicate=predicate,
                value=obj,
            )
        )
    for predicate, literal in term.iterate_literal_properties():
        properties.append(
            og.StandardizedProperty(
                predicate=predicate,
                value=literal.value,
            )
        )
    return properties or None


def _get_xrefs(stanza: Stanza) -> list[og.StandardizedXref] | None:
    return [og.StandardizedXref(reference=xref) for xref in stanza.xrefs] or None


def _meta_or_none(meta: og.StandardizedMeta) -> og.StandardizedMeta | None:
    if all(
        x is None
        for x in (
            meta.definition,
            meta.subsets,
            meta.xrefs,
            meta.synonyms,
            meta.comments,
            meta.version_iri,
            meta.properties,
        )
    ):
        return None
    return meta


def _get_class_node(term: Term) -> og.StandardizedNode:
    meta = og.StandardizedMeta(
        definition=_get_definition(term),
        subsets=term.subsets or None,
        xrefs=_get_xrefs(term),
        synonyms=_get_synonyms(term),
        comments=term.get_comments() or None,
        deprecated=term.is_obsolete or False,
        properties=_get_properties(term),
    )
    return og.StandardizedNode(
        reference=term.reference,
        label=term.name,
        meta=_meta_or_none(meta),
        type="CLASS" if term.type == "Term" else "INDIVIDUAL",
    )


def _get_typedef_node(typedef: TypeDef) -> og.StandardizedNode:
    meta = og.StandardizedMeta(
        definition=_get_definition(typedef),
        subsets=typedef.subsets or None,
        xrefs=_get_xrefs(typedef),
        synonyms=_get_synonyms(typedef),
        comments=typedef.get_comments() or None,
        deprecated=typedef.is_obsolete or False,
        properties=_get_properties(typedef),
    )
    return og.StandardizedNode(
        reference=typedef.reference,
        label=typedef.name,
        meta=_meta_or_none(meta),
        type="PROPERTY",
        property_type="ANNOTATION" if typedef.is_metadata_tag else "OBJECT",
    )


def _get_edges(obo: Obo) -> list[og.StandardizedEdge]:
    rv = [
        og.StandardizedEdge(
            subject=stanza.reference,
            predicate=typedef.reference,
            object=target,
        )
        for stanza, typedef, target in obo.iterate_edges(include_xrefs=False)
    ]
    return rv
