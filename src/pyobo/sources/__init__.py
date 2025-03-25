"""Sources of OBO content."""

from class_resolver import ClassResolver

from .antibodyregistry import AntibodyRegistryGetter
from .bigg import BiGGCompartmentGetter, BiGGMetaboliteGetter, BiGGModelGetter, BiGGReactionGetter
from .ccle import CCLEGetter
from .cgnc import CGNCGetter
from .chembl import ChEMBLCompoundGetter, ChEMBLTargetGetter
from .civic_gene import CIVICGeneGetter
from .clinicaltrials import ClinicalTrialsGetter
from .complexportal import ComplexPortalGetter
from .conso import CONSOGetter
from .cpt import CPTGetter
from .credit import CreditGetter
from .cvx import CVXGetter
from .depmap import DepMapGetter
from .dictybase_gene import DictybaseGetter
from .drugbank import DrugBankGetter, DrugBankSaltGetter
from .drugcentral import DrugCentralGetter
from .expasy import ExpasyGetter
from .famplex import FamPlexGetter
from .flybase import FlyBaseGetter
from .gard import GARDGetter
from .geonames import GeonamesFeatureGetter, GeonamesGetter
from .gtdb import GTDBGetter
from .gwascentral import GWASCentralPhenotypeGetter, GWASCentralStudyGetter
from .hgnc import HGNCGetter, HGNCGroupGetter
from .icd import ICD10Getter, ICD11Getter
from .interpro import InterProGetter
from .itis import ITISGetter
from .kegg import KEGGGeneGetter, KEGGGenomeGetter, KEGGPathwayGetter
from .mesh import MeSHGetter
from .mgi import MGIGetter
from .mirbase import MiRBaseFamilyGetter, MiRBaseGetter, MiRBaseMatureGetter
from .msigdb import MSigDBGetter
from .ncbi import NCBIGCGetter, NCBIGeneGetter
from .nih_reporter import NIHReporterGetter
from .nlm import NLMCatalogGetter, NLMPublisherGetter
from .npass import NPASSGetter
from .omim_ps import OMIMPSGetter
from .pathbank import PathBankGetter
from .pfam import PfamClanGetter, PfamGetter
from .pharmgkb import (
    PharmGKBChemicalGetter,
    PharmGKBDiseaseGetter,
    PharmGKBGeneGetter,
    PharmGKBPathwayGetter,
    PharmGKBVariantGetter,
)
from .pid import PIDGetter
from .pombase import PomBaseGetter
from .pubchem import PubChemCompoundGetter
from .reactome import ReactomeGetter
from .rgd import RGDGetter
from .rhea import RheaGetter
from .ror import RORGetter
from .selventa import SCHEMGetter, SCOMPGetter, SDISGetter, SFAMGetter
from .sgd import SGDGetter
from .signor import SignorGetter
from .slm import SLMGetter
from .umls import UMLSGetter, UMLSSTyGetter
from .unimod import UnimodGetter
from .uniprot import UniProtGetter, UniProtPtmGetter
from .wikipathways import WikiPathwaysGetter
from .zfin import ZFINGetter
from ..struct.struct import AdHocOntologyBase, Obo

__all__ = [
    "AntibodyRegistryGetter",
    "BiGGCompartmentGetter",
    "BiGGMetaboliteGetter",
    "BiGGModelGetter",
    "BiGGReactionGetter",
    "CCLEGetter",
    "CGNCGetter",
    "CIVICGeneGetter",
    "CONSOGetter",
    "CPTGetter",
    "CVXGetter",
    "ChEMBLCompoundGetter",
    "ChEMBLTargetGetter",
    "ClinicalTrialsGetter",
    "ComplexPortalGetter",
    "CreditGetter",
    "DepMapGetter",
    "DictybaseGetter",
    "DrugBankGetter",
    "DrugBankSaltGetter",
    "DrugCentralGetter",
    "ExpasyGetter",
    "FamPlexGetter",
    "FlyBaseGetter",
    "GARDGetter",
    "GTDBGetter",
    "GWASCentralPhenotypeGetter",
    "GWASCentralStudyGetter",
    "GeonamesFeatureGetter",
    "GeonamesGetter",
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
    "NCBIGCGetter",
    "NCBIGeneGetter",
    "NIHReporterGetter",
    "NLMCatalogGetter",
    "NLMPublisherGetter",
    "NPASSGetter",
    "OMIMPSGetter",
    "PIDGetter",
    "PathBankGetter",
    "PfamClanGetter",
    "PfamGetter",
    "PharmGKBChemicalGetter",
    "PharmGKBDiseaseGetter",
    "PharmGKBGeneGetter",
    "PharmGKBPathwayGetter",
    "PharmGKBVariantGetter",
    "PomBaseGetter",
    "PubChemCompoundGetter",
    "RGDGetter",
    "RORGetter",
    "ReactomeGetter",
    "RheaGetter",
    "SCHEMGetter",
    "SCOMPGetter",
    "SDISGetter",
    "SFAMGetter",
    "SGDGetter",
    "SLMGetter",
    "SignorGetter",
    "UMLSGetter",
    "UMLSSTyGetter",
    "UniProtGetter",
    "UniProtPtmGetter",
    "UnimodGetter",
    "WikiPathwaysGetter",
    "ZFINGetter",
    "ontology_resolver",
]

ontology_resolver: ClassResolver[Obo] = ClassResolver.from_subclasses(
    base=Obo,
    suffix="Getter",
    skip={AdHocOntologyBase},
)
for getter in list(ontology_resolver):
    ontology_resolver.synonyms[getter.ontology] = getter
