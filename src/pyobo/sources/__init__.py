# -*- coding: utf-8 -*-

"""Sources of OBO content."""

from class_resolver import Resolver

from .antibodyregistry import AntibodyRegistryGetter
from .ccle import CCLEGetter
from .cgnc import CGNCGetter
from .chembl import ChEBMLGetter
from .complexportal import ComplexPortalGetter
from .conso import CONSOGetter
from .depmap import DepMapGetter
from .dictybase_gene import DictybaseGetter
from .drugbank import DrugBankGetter
from .drugbank_salt import DrugBankSaltGetter
from .drugcentral import DrugCentralGetter
from .expasy import ExpasyGetter
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
    "AntibodyRegistryGetter",
    "CCLEGetter",
    "CGNCGetter",
    "ChEBMLGetter",
    "ComplexPortalGetter",
    "CONSOGetter",
    "DepMapGetter",
    "DictybaseGetter",
    "DrugBankGetter",
    "DrugBankSaltGetter",
    "DrugCentralGetter",
    "ExpasyGetter",
    "FlyBaseGetter",
    "GWASCentralPhenotypeGetter",
    "GWASCentralStudyGetter",
    "HGNCGetter",
    "MGIGetter",
    "UMLSGetter",
    "UniProtGetter",
]

ontology_resolver = Resolver.from_subclasses(base=Obo, suffix="Getter")
