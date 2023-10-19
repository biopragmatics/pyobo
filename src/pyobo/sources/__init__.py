# -*- coding: utf-8 -*-

"""Sources of OBO content."""

from class_resolver import ClassResolver

from .antibodyregistry import AntibodyRegistryGetter
from .ccle import CCLEGetter
from .cgnc import CGNCGetter
from .chembl import ChEMBLCompoundGetter
from .complexportal import ComplexPortalGetter
from .conso import CONSOGetter
from .cpt import CPTGetter
from .cvx import CVXGetter
from .depmap import DepMapGetter
from .dictybase_gene import DictybaseGetter
from .drugbank import DrugBankGetter
from .drugbank_salt import DrugBankSaltGetter
from .drugcentral import DrugCentralGetter
from .expasy import ExpasyGetter
from .famplex import FamPlexGetter
from .flybase import FlyBaseGetter
from .gwascentral_phenotype import GWASCentralPhenotypeGetter
from .gwascentral_study import GWASCentralStudyGetter
from .hgnc import HGNCGetter
from .hgncgenefamily import HGNCGroupGetter
from .icd10 import ICD10Getter
from .icd11 import ICD11Getter
from .interpro import InterProGetter
from .itis import ITISGetter
from .kegg import KEGGGeneGetter, KEGGGenomeGetter, KEGGPathwayGetter
from .mesh import MeSHGetter
from .mgi import MGIGetter
from .mirbase import MiRBaseGetter
from .mirbase_family import MiRBaseFamilyGetter
from .mirbase_mature import MiRBaseMatureGetter
from .msigdb import MSigDBGetter
from .ncbigene import NCBIGeneGetter
from .npass import NPASSGetter
from .pathbank import PathBankGetter
from .pfam import PfamGetter
from .pfam_clan import PfamClanGetter
from .pid import PIDGetter
from .pombase import PomBaseGetter
from .pubchem import PubChemCompoundGetter
from .reactome import ReactomeGetter
from .rgd import RGDGetter
from .rhea import RheaGetter
from .selventa import SCHEMGetter, SCOMPGetter, SDISGetter, SFAMGetter
from .sgd import SGDGetter
from .slm import SLMGetter
from .umls import UMLSGetter
from .uniprot import UniProtGetter, UniProtPtmGetter
from .wikipathways import WikiPathwaysGetter
from .zfin import ZFINGetter
from ..struct import Obo

__all__ = [
    "AntibodyRegistryGetter",
    "CCLEGetter",
    "CGNCGetter",
    "CONSOGetter",
    "CPTGetter",
    "CVXGetter",
    "ChEMBLCompoundGetter",
    "ComplexPortalGetter",
    "DepMapGetter",
    "DictybaseGetter",
    "DrugBankGetter",
    "DrugBankSaltGetter",
    "DrugCentralGetter",
    "ExpasyGetter",
    "FamPlexGetter",
    "FlyBaseGetter",
    "GWASCentralPhenotypeGetter",
    "GWASCentralStudyGetter",
    "HGNCGetter",
    "HGNCGroupGetter",
    "ICD10Getter",
    "ICD11Getter",
    "ITISGetter",
    "InterProGetter",
    "KEGGGeneGetter",
    "KEGGGenomeGetter",
    "KEGGPathwayGetter",
    "MGIGetter",
    "MSigDBGetter",
    "MeSHGetter",
    "MiRBaseFamilyGetter",
    "MiRBaseGetter",
    "MiRBaseMatureGetter",
    "NCBIGeneGetter",
    "NPASSGetter",
    "PIDGetter",
    "PathBankGetter",
    "PfamClanGetter",
    "PfamGetter",
    "PomBaseGetter",
    "PubChemCompoundGetter",
    "RGDGetter",
    "ReactomeGetter",
    "RheaGetter",
    "SCHEMGetter",
    "SCOMPGetter",
    "SDISGetter",
    "SFAMGetter",
    "SGDGetter",
    "SLMGetter",
    "UMLSGetter",
    "UniProtGetter",
    "UniProtPtmGetter",
    "WikiPathwaysGetter",
    "ZFINGetter",
    "ontology_resolver",
]


def _assert_sorted():
    _sorted = sorted(__all__)
    if _sorted != __all__:
        raise ValueError(f"unsorted. should be:\n{_sorted}")


_assert_sorted()
del _assert_sorted

ontology_resolver: ClassResolver[Obo] = ClassResolver.from_subclasses(base=Obo, suffix="Getter")
for getter in list(ontology_resolver):
    ontology_resolver.synonyms[getter.ontology] = getter
