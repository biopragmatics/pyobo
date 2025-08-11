"""API for grounding relations."""

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import requests
from bioregistry import NormalizedNamedReference
from tqdm import tqdm

__all__ = [
    "get_normalized_label",
    "ground_relation",
]

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("data.json")
URLS = [
    ("ro", "http://purl.obolibrary.org/obo/ro.json"),
    (
        "debio",
        "https://raw.githubusercontent.com/biopragmatics/debio/main/releases/current/debio.json",
    ),
    ("bfo", None),
    ("oboinowl", None),
    ("bspo", None),
    ("iao", None),
    ("omo", None),
    ("vo", None),
    ("obi", None),
]
PREFIX_OBO = "http://purl.obolibrary.org/obo/"
PREFIX_OIO = "http://www.geneontology.org/formats/oboInOwl#"

LABELS = {
    "http://www.w3.org/2000/01/rdf-schema#isDefinedBy": "is_defined_by",
    "rdf:type": "type",
    "owl:inverseOf": "inverse_of",
    "skos:exactMatch": "exact_match",
    "rdfs:subClassOf": "is_a",
    "rdfs:subPropertyOf": "subproperty",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
    "obo:has_prefix": "has_unit_prefix",  # weird thing from UO
    # FIXME deal with these relations
    "http://purl.obolibrary.org/obo/uberon/core#proximally_connected_to": "proximally_connected_to",
    "http://purl.obolibrary.org/obo/uberon/core#extends_fibers_into": "proximally_connected_to",
    "http://purl.obolibrary.org/obo/uberon/core#channel_for": "proximally_connected_to",
    "http://purl.obolibrary.org/obo/uberon/core#distally_connected_to": "proximally_connected_to",
    "http://purl.obolibrary.org/obo/uberon/core#channels_into": "channels_into",
    "http://purl.obolibrary.org/obo/uberon/core#channels_from": "channels_from",
    "http://purl.obolibrary.org/obo/uberon/core#subdivision_of": "subdivision_of",
    "http://purl.obolibrary.org/obo/uberon/core#protects": "protects",
    "http://purl.obolibrary.org/obo/uberon/core#posteriorly_connected_to": "posteriorly_connected_to",
    "http://purl.obolibrary.org/obo/uberon/core#evolved_from": "evolved_from",
    "http://purl.obolibrary.org/obo/uberon/core#anteriorly_connected_to": "anteriorly_connected_to",
    #
    "obi:0000304": "is_manufactured_by",
    "vo:0003355": "immunizes_against_microbe",
    "bao:0002846": "has_assay_protocol",
}


def _norm(s: str) -> str:
    return s.replace(" ", "").replace("_", "").replace(":", "").lower()


def ground_relation(s: str) -> NormalizedNamedReference | None:
    """Ground a string to a RO property."""
    return get_lookups().get(_norm(s))


def get_normalized_label(curie_or_uri: str) -> str | None:
    """Get a normalized label."""
    rv = LABELS.get(curie_or_uri)
    if rv:
        return rv
    rv = get_curie_to_norm_name().get(curie_or_uri)
    if rv:
        return rv
    return None


@lru_cache(1)
def get_lookups() -> Mapping[str, NormalizedNamedReference]:
    """Get lookups for relation ontology properties."""
    d = {}
    for record in json.loads(PATH.read_text()):
        prefix, identifier, label = record["prefix"], record["identifier"], record["label"]
        d[_norm(label)] = NormalizedNamedReference(prefix=prefix, identifier=identifier, name=label)
        for s in record.get("synonyms", []):
            d[_norm(s)] = NormalizedNamedReference(prefix=prefix, identifier=identifier, name=label)
    return d


def label_norm(s: str) -> str:
    """Normalize a label string."""
    return s.lower().replace(" ", "_")


@lru_cache(1)
def get_curie_to_norm_name() -> Mapping[str, str]:
    """Get a dictionary mapping CURIEs to their normalized names."""
    curie_to_norm_name = {}
    for record in json.loads(PATH.read_text()):
        prefix, identifier, label = record["prefix"], record["identifier"], record["label"]
        curie_to_norm_name[f"{prefix}:{identifier}"] = label_norm(label)
    return curie_to_norm_name


HEADER = ["prefix", "identifier", "label", "synonyms"]


def main():
    """Download and process the relation ontology data."""
    from bioontologies import get_obograph_by_prefix
    from bioontologies.obograph import GraphDocument
    from bioontologies.robot import correct_raw_json

    rows = []
    for source, url in URLS:
        if url is not None:
            res = requests.get(url, timeout=60)
            res.raise_for_status()
            res_json = res.json()
            correct_raw_json(res_json)
            graph_document = GraphDocument.model_validate(res_json)
            graph = graph_document.guess(source)
        else:
            try:
                results = get_obograph_by_prefix(source)
                graph = results.guess(source)
            except ValueError as e:
                tqdm.write(f"[{source}] error: {e}")
                continue
        for node in tqdm(graph.nodes, desc=source, unit="node"):
            if node.type != "PROPERTY" or not node.name:
                continue
            node.standardize()
            if not node.prefix:
                tqdm.write(f"[{source}] could not parse node: {node.id}")
                continue
            rows.append(
                (
                    node.prefix,
                    node.identifier,
                    node.name,
                    tuple(sorted(synonym.value for synonym in node.synonyms)),
                )
            )

    for p in ["rdf", "rdfs", "owl"]:
        j = json.loads(HERE.joinpath(f"data_{p}.json").read_text())
        rows.extend(tuple(row.get(h, ()) for h in HEADER) for row in j)

    rows = sorted(set(rows))
    row_dicts = [{k: v for k, v in zip(HEADER, row, strict=False) if v} for row in rows]
    PATH.write_text(json.dumps(row_dicts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
