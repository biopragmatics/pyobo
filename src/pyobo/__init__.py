"""A python package for handling and generating OBO."""

from .api import (
    get_alts_to_id,
    get_ancestors,
    get_children,
    get_definition,
    get_descendants,
    get_edges,
    get_edges_df,
    get_filtered_properties_df,
    get_filtered_properties_mapping,
    get_filtered_properties_multimapping,
    get_filtered_relations_df,
    get_filtered_xrefs,
    get_graph,
    get_hierarchy,
    get_id_definition_mapping,
    get_id_multirelations_mapping,
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_ids,
    get_literal_mappings,
    get_literal_mappings_df,
    get_literal_mappings_subset,
    get_literal_properties,
    get_literal_properties_df,
    get_mappings_df,
    get_metadata,
    get_name,
    get_name_by_curie,
    get_name_id_mapping,
    get_object_properties,
    get_object_properties_df,
    get_obsolete,
    get_primary_curie,
    get_primary_identifier,
    get_properties,
    get_properties_df,
    get_property,
    get_references,
    get_relation,
    get_relation_mapping,
    get_relations_df,
    get_species,
    get_sssom_df,
    get_subhierarchy,
    get_synonyms,
    get_text_embedding,
    get_text_embedding_similarity,
    get_typedef_df,
    get_xref,
    get_xrefs,
    get_xrefs_df,
    has_ancestor,
    is_descendent,
)
from .getters import get_ontology
from .ner import get_grounder, ground
from .plugins import (
    has_nomenclature_plugin,
    iter_nomenclature_plugins,
    run_nomenclature_plugin,
)
from .struct import (
    Obo,
    Reference,
    StanzaType,
    Synonym,
    SynonymTypeDef,
    Term,
    TypeDef,
    build_ontology,
    default_reference,
)
from .struct.obo import from_obo_path, from_obonet
from .utils.path import ensure_path
from .version import get_version

__all__ = [
    "Obo",
    "Reference",
    "StanzaType",
    "Synonym",
    "SynonymTypeDef",
    "Term",
    "TypeDef",
    "build_ontology",
    "default_reference",
    "ensure_path",
    "from_obo_path",
    "from_obonet",
    "get_alts_to_id",
    "get_ancestors",
    "get_children",
    "get_definition",
    "get_descendants",
    "get_edges",
    "get_edges_df",
    "get_filtered_properties_df",
    "get_filtered_properties_mapping",
    "get_filtered_properties_multimapping",
    "get_filtered_relations_df",
    "get_filtered_xrefs",
    "get_graph",
    "get_grounder",
    "get_hierarchy",
    "get_id_definition_mapping",
    "get_id_multirelations_mapping",
    "get_id_name_mapping",
    "get_id_species_mapping",
    "get_id_synonyms_mapping",
    "get_id_to_alts",
    "get_ids",
    "get_literal_mappings",
    "get_literal_mappings_df",
    "get_literal_mappings_subset",
    "get_literal_properties",
    "get_literal_properties_df",
    "get_mappings_df",
    "get_metadata",
    "get_name",
    "get_name_by_curie",
    "get_name_id_mapping",
    "get_object_properties",
    "get_object_properties_df",
    "get_obsolete",
    "get_ontology",
    "get_primary_curie",
    "get_primary_identifier",
    "get_properties",
    "get_properties_df",
    "get_property",
    "get_references",
    "get_relation",
    "get_relation_mapping",
    "get_relations_df",
    "get_species",
    "get_sssom_df",
    "get_subhierarchy",
    "get_synonyms",
    "get_text_embedding",
    "get_text_embedding_similarity",
    "get_typedef_df",
    "get_version",
    "get_xref",
    "get_xrefs",
    "get_xrefs_df",
    "ground",
    "has_ancestor",
    "has_nomenclature_plugin",
    "is_descendent",
    "iter_nomenclature_plugins",
    "run_nomenclature_plugin",
]
