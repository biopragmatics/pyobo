"""Converter for ChEBI."""

from collections.abc import Mapping

from ..api import get_filtered_properties_mapping, get_filtered_relations_df
from ..struct import Reference, TypeDef
from ..utils.io import multisetdict

__all__ = [
    "get_chebi_id_smiles_mapping",
    "get_chebi_role_to_children",
    "get_chebi_smiles_id_mapping",
]


def get_chebi_id_smiles_mapping(**kwargs) -> Mapping[str, str]:
    """Get a mapping from ChEBI identifiers to SMILES.

    This is common enough that it gets its own function :)
    """
    return get_filtered_properties_mapping(
        "chebi", "http://purl.obolibrary.org/obo/chebi/smiles", **kwargs
    )


def get_chebi_smiles_id_mapping() -> Mapping[str, str]:
    """Get a mapping from sSMILES to ChEBI identifiers."""
    return {v: k for k, v in get_chebi_id_smiles_mapping().items()}


has_role = TypeDef(reference=Reference(prefix="chebi", identifier="has_role"))


def get_chebi_role_to_children() -> Mapping[str, set[tuple[str, str]]]:
    """Get the ChEBI role to children mapping."""
    df = get_filtered_relations_df("chebi", relation=has_role)
    return multisetdict((role_id, ("chebi", chemical_id)) for chemical_id, _, role_id in df.values)
