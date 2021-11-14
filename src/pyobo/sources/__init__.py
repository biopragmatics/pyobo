# -*- coding: utf-8 -*-

"""Sources of OBO content."""

from class_resolver import Resolver

from .cgnc import CGNCGetter
from .chembl import ChEBMLGetter
from .complexportal import ComplexPortalGetter
from .flybase import FlyBaseGetter
from .gwascentral_phenotype import GWASCentralPhenotypeGetter
from .gwascentral_study import GWASCentralStudyGetter
from .hgnc import HGNCGetter
from .mgi import MGIGetter
from .umls import UMLSGetter
from .uniprot import UniProtGetter
from ..struct import Obo

__all__ = [
    "ontology_resolver",
    # Getters
    "CGNCGetter",
    "ChEBMLGetter",
    "ComplexPortalGetter",
    "FlyBaseGetter",
    "GWASCentralPhenotypeGetter",
    "GWASCentralStudyGetter",
    "HGNCGetter",
    "MGIGetter",
    "UMLSGetter",
    "UniProtGetter",
]

ontology_resolver = Resolver.from_subclasses(base=Obo, suffix="Getter")
