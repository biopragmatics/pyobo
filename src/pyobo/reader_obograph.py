import json
import logging
from pathlib import Path
from typing import Optional, Union

import bioregistry

from .constants import DATE_FORMAT, PROVENANCE_PREFIXES
from .identifier_utils import MissingPrefix, normalize_curie
from .registries import curie_has_blacklisted_prefix, curie_is_blacklisted, remap_prefix
from .struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    TypeDef,
    make_ad_hoc_ontology,
)
from .struct.typedef import default_typedefs, develops_from, has_part, part_of
from .utils.misc import cleanup_version

__all__ = [
    "from_obo_json_path",
]

logger = logging.getLogger(__name__)


def from_obo_json_path(
    path: Union[str, Path], prefix: Optional[str] = None, *, strict: bool = True
) -> Obo:
    graphs = json.loads(Path(path).read_text())["graphs"]
    if len(graphs) != 1:
        raise ValueError
    graph = graphs[0]

    return make_ad_hoc_ontology(
        _ontology=prefix,
        _name=_get_graph_name(graph),
        _data_version=_get_graph_version(graph),
        terms=list(_iter_nodes(graph)),
    )


def _iter_nodes(graph):
    for node in graph["nodes"]:
        iri = node["id"]
        prefix, identifier = bioregistry.parse_iri(iri)
        if prefix is None or identifier is None:
            logger.warning("could not parse IRI: %s", iri)
            continue
        term = Term.from_triple(
            prefix=prefix,
            identifier=identifier,
            name=node.get("lbl"),
        )
        term.definition = _get_description(node)
        # TODO add synonyms, xrefs, parents, etc.
        yield term


def _get_description(node) -> Optional[str]:
    return _get_meta(node, "http://purl.org/dc/terms/description")


def _get_graph_description(graph) -> Optional[str]:
    return _get_meta(graph, "http://purl.obolibrary.org/obo/IAO_0000119")


def _get_graph_name(graph) -> Optional[str]:
    return _get_meta(graph, "http://purl.org/dc/terms/title")


def _get_graph_version(graph) -> Optional[str]:
    return _get_meta(graph, "http://www.w3.org/2002/07/owl#versionInfo")


def _get_graph_version_iri(graph) -> Optional[str]:
    return graph.get("meta", {}).get("version")


def _get_meta(element, key: str) -> Optional[str]:
    for v in element.get("meta", {}).get("basicPropertyValues", []):
        if v["pred"] == key:
            return v["val"]
    return None
