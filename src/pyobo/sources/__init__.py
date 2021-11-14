# -*- coding: utf-8 -*-

"""Sources of OBO content."""

from class_resolver import Resolver

from .cgnc import CGNCGetter
from .chembl import ChEBMLGetter
from .complexportal import ComplexPortalGetter
from .umls import UMLSGetter
from .uniprot import UniProtGetter
from ..struct import Obo

__all__ = [
    "ontology_resolver",
    # Getters
    "CGNCGetter",
    "ChEBMLGetter",
    "ComplexPortalGetter",
    "UMLSGetter",
    "UniProtGetter",
]

ontology_resolver = Resolver.from_subclasses(base=Obo, suffix="Getter")
