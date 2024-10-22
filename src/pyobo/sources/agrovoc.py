"""Converter for AGROVOC."""

import pystow
from pystow.utils import read_zipfile_rdf
from rdflib import Graph
from rdflib.namespace import DCTERMS, SKOS

__all__ = [
    "ensure_agrovoc_graph",
]

PREFIX = "agrovoc"


def ensure_agrovoc_graph(version: str) -> Graph:
    """Download and parse the given version of AGROVOC."""
    url = f"https://agrovoc.fao.org/agrovocReleases/agrovoc_{version}_core.nt.zip"
    path = pystow.ensure("bio", "agrovoc", version, url=url, name="core.nt.zip")
    graph = read_zipfile_rdf(path, inner_path=f"agrovoc_{version}_core.nt", format="nt")
    graph.bind("skosxl", "http://www.w3.org/2008/05/skos-xl#")
    graph.bind("skos", SKOS)
    graph.bind("dcterms", DCTERMS)
    graph.bind(PREFIX, "http://aims.fao.org/aos/agrontology#")
    return graph
