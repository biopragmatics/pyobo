# -*- coding: utf-8 -*-

"""A python package for handling and generating OBO."""

from .api import (  # noqa: F401
    get_alts_to_id,
    get_ancestors,
    get_definition,
    get_descendants,
    get_filtered_properties_df,
    get_filtered_properties_mapping,
    get_filtered_properties_multimapping,
    get_filtered_relations_df,
    get_filtered_xrefs,
    get_hierarchy,
    get_id_definition_mapping,
    get_id_multirelations_mapping,
    get_id_name_mapping,
    get_id_species_mapping,
    get_id_synonyms_mapping,
    get_id_to_alts,
    get_name,
    get_name_by_curie,
    get_name_id_mapping,
    get_primary_curie,
    get_primary_identifier,
    get_properties,
    get_properties_df,
    get_property,
    get_relation,
    get_relation_mapping,
    get_relations_df,
    get_species,
    get_subhierarchy,
    get_synonyms,
    get_typedef_df,
    get_xref,
    get_xrefs_df,
    has_ancestor,
    is_descendent,
)
from .getters import get_ontology  # noqa: F401
from .identifier_utils import normalize_curie, normalize_prefix  # noqa: F401
from .normalizer import OboNormalizer, ground  # noqa: F401
from .sources import (  # noqa: F401
    has_nomenclature_plugin,
    iter_nomenclature_plugins,
    run_nomenclature_plugin,
)
from .struct import Obo, Reference, Synonym, SynonymTypeDef, Term, TypeDef  # noqa: F401
from .utils.path import ensure_path  # noqa: F401
from .version import get_version  # noqa: F401
from .xrefdb.canonicalizer import Canonicalizer, get_equivalent, get_priority_curie  # noqa: F401
from .xrefdb.sources import has_xref_plugin, iter_xref_plugins, run_xref_plugin  # noqa: F401
