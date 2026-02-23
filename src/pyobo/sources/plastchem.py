"""Import PlastChem."""

import textwrap
from collections import Counter
from collections.abc import Iterable
from typing import Any

import pandas as pd
import ssslm
from tabulate import tabulate
from tqdm import tqdm

from pyobo import Obo, get_grounder
from pyobo.struct import Reference, Term, default_reference
from pyobo.struct.typedef import (
    exact_match,
    has_canonical_smiles,
    has_inchi,
    has_isomeric_smiles,
    has_role,
    member_of,
)
from pyobo.struct.vocabulary import chemical
from pyobo.utils.path import ensure_path

__all__ = ["PlastChemGetter"]

PREFIX = "plastchem"
URL = "https://zenodo.org/records/10701706/files/plastchem_db_v1.0.xlsx?download=1"
VERSION = "1.0"

# See page 45 of the report for explanation
HAZARD_LISTS = {
    "Red": "chemicals of concern",
    # The Red List contains the 3651 chemicals of concern that are currently not regulated internationally. These chemicals are hazardous according to well-established criteria (one or more hazard criteria) and should be regulated.
    "Orange": "less hazardous",
    # The Orange List covers 1168 chemicals that have been classified as less hazardous (e.g., carcinogenic, mutagenic category 2). They may be further watched, as additional hazard traits may be identified.
    "Watch": "under assessment",
    # For the 28 chemicals on the Watch List, a hazard evaluation is currently under development or inconclusive. Similar to the Orange List, it includes chemicals that have potential to become chemicals of concern once fully assessed.
    "White": "not hazardous",
    # The chemicals on the White List are classified as not hazardous but their hazard profiles are incomplete. While there is some level of evidence that White List chemicals are not of concern, the incomplete hazard assessment warrants prioritization for further evaluation to provide a complete hazard profile.
    "Grey": "no hazard data",
    # The largest list, the Grey List, includes 10 345 plastic chemicals without hazard information. Those chemicals constitute the biggest knowledge gap as their hazard properties are unknown based on the authoritative sources consulted. In the absence of this information, no regulatory action is possible at this point.
    "MEA": "regulated globally",  # Basel, Stochholm, Minamata
}
HAZARD_LIST_REFERENCES = {
    f"{list_color}_list": default_reference(
        PREFIX, f"{list_color}_list", f"PlastChem {list_color} List"
    )
    for list_color in HAZARD_LISTS
}

HAZARD_LIST_ROOT = default_reference(PREFIX, "list", "PlastChem List")


class PlastChemGetter(Obo):
    """An ontology representation of PlastChem."""

    ontology = PREFIX
    static_version = VERSION
    typedefs = [
        has_inchi,
        has_canonical_smiles,
        has_isomeric_smiles,
        exact_match,
        has_role,
        member_of,
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Do it."""
    yield Term(reference=chemical)
    yield Term(reference=HAZARD_LIST_ROOT)
    for chebi_role in CHEBI_ROLE_MAP.values():
        yield Term(reference=chebi_role)
    for echa_reference_def in ECHA_MAP.values():
        yield Term(reference=echa_reference_def)
    for hazard_list_reference in HAZARD_LIST_REFERENCES.values():
        term = Term(reference=hazard_list_reference)
        term.append_parent(HAZARD_LIST_ROOT)
        yield term

    echa_counter: Counter[str] = Counter()
    echa_examples = {}
    function_counter: Counter[str] = Counter()
    function_examples = {}
    chebi_grounder = get_grounder("chebi")

    path = ensure_path(PREFIX, url=URL, version=VERSION)
    df = pd.read_excel(path, sheet_name="Full database", dtype=str, skiprows=1)
    # TODO group by CAS number and add alt-id annotations
    for _, row in df.iterrows():
        identifier = row["plastchem_ID"]
        if pd.isna(identifier):
            continue

        name: str | None
        if pd.notna(row["pubchem_name"]):
            name = row["pubchem_name"]
        elif pd.notna(row["iupac_name"]):
            name = row["iupac_name"]
        else:
            name = None
        term = Term.from_triple(PREFIX, identifier, name).append_parent(chemical)

        cas = row.pop("cas")
        cas_fixed = row.pop("cas_fixed")
        if pd.notna(cas_fixed) and pd.notna(cas):
            if cas != cas_fixed.lstrip("'"):
                tqdm.write(f"[plastchem:{identifier}] has mismached CAS: {cas} and {cas_fixed}")
            else:
                term.append_exact_match(Reference(prefix="cas", identifier=cas))

        if pd.notna(pubchem_id := row.pop("pubchem_cid")):
            term.append_exact_match(Reference(prefix="pubchem", identifier=pubchem_id))

        if pd.notna(canonical_smiles := row.pop("canonical_smiles")):
            term.annotate_string(has_canonical_smiles, canonical_smiles)
        if pd.notna(isomeric_smiles := row.pop("isomeric_smiles")):
            term.annotate_string(has_isomeric_smiles, isomeric_smiles)
        if pd.notna(inchi := row.pop("inchi")):
            term.annotate_string(has_inchi, inchi)
        if pd.notna(inchikey := row.pop("inchikey")):
            term.append_exact_match(Reference(prefix="inchikey", identifier=inchikey))

        if pd.notna(echa_grouping := row.pop("ECHA_grouping")):
            echa_counter[echa_grouping] += 1
            if echa_grouping not in echa_examples:
                if echa_reference := _ground_echa(chebi_grounder, echa_grouping):
                    echa_examples[echa_grouping] = echa_reference.curie, echa_reference.name
                    term.append_parent(echa_reference)
                else:
                    pass  # needs curating...

        if pd.notna(plastchem_list := row.pop("PlastChem_lists")):
            term.append_relationship(member_of, HAZARD_LIST_REFERENCES[plastchem_list])

        # NIAS means non-intentionally added substance
        for func in _get_sep(row, "Harmonized_functions"):
            func = func.replace("_", " ").lower()
            if role := CHEBI_ROLE_MAP.get(func):
                term.append_relationship(has_role, role)

            function_counter[func] += 1
            if func not in function_examples and name is not None:
                if reference := chebi_grounder.get_best_match(name):
                    if reference.curie != "chebi:15702":
                        function_examples[func] = reference.curie, reference.name
                elif reference := chebi_grounder.get_best_match(name.rstrip("s")):
                    if reference.curie != "chebi:15702":
                        function_examples[func] = reference.curie, reference.name

        # TODO check if the `Harmonized_functions` is just actually
        #  the union of the following:
        #  - original_function_plasticmap
        #  - original_function_cpp
        #  - original_primary_function_aurisano
        #  - original_other_function_aurisano
        #  - industrial_sector_plasticmap

        yield term

    tqdm.write(
        tabulate(
            [
                (
                    textwrap.shorten(echa_name, 100),
                    m.curie if (m := chebi_grounder.get_best_match(echa_name)) else None,
                    count,
                )
                for echa_name, count in echa_counter.most_common()
            ],
            headers=["ECHA", "chebi", "count"],
            tablefmt="github",
        )
    )
    tqdm.write("")

    rows = [
        (
            function_name,
            function_curie.curie if (function_curie := CHEBI_ROLE_MAP.get(function_name)) else "",
            *function_examples.get(function_name, (None, None)),
            count,
        )
        for function_name, count in function_counter.most_common()
    ]
    rows = [r for r in rows if not r[1]]
    tqdm.write(
        tabulate(
            rows,
            headers=["function", "chebi", "example_chebi", "example_chebi_name", "count"],
        )
    )


def _ground_echa(chebi_grounder: ssslm.Grounder, echa_grouping: str) -> Reference | None:
    echa_grouping = echa_grouping.strip()
    if echa_grouping in ECHA_MAP:
        return ECHA_MAP[echa_grouping]
    if match := chebi_grounder.get_best_match(echa_grouping):
        return Reference.from_reference(match.reference)
    elif match := chebi_grounder.get_best_match(echa_grouping.rstrip("s")):
        return Reference.from_reference(match.reference)
    return None


# TODO curate links from all ECHA terms back to ChEBI terms


"""
| ECHA                                                                                                | chebi        |   count |
|-----------------------------------------------------------------------------------------------------|--------------|---------|
| Isocyanates                                                                                         | chebi:53212  |      55 |
| Ortho-phthalates                                                                                    |              |      53 |
| Acrylates and methacrylates with linear or branched aliphatic alcohols, simple acids and salts      |              |      46 |
| Bisphenol A (BPA) derivatives                                                                       |              |      41 |
| Resin and rosin acids and their derivatives                                                         |              |      40 |
| Esters from acrylic and methacrylic acid and aliphatic cyclic alcohols, polyols and ether [...]     |              |      38 |
| Branched carboxylic acids and its salts                                                             |              |      38 |
| Isophthalates, Terephthalates and Trimellitates                                                     |              |      29 |
| Glycidyl ethers and esters                                                                          |              |      28 |
| primary aliphatic diamines and their salts                                                          |              |      28 |
| Phthalic anhydrides and hydrogenated phthalic anhydrides                                            |              |      28 |
| Simple inorganic silicon compounds                                                                  |              |      26 |
| chlorinated aromatic hydrocarbons                                                                   |              |      24 |
| hydrocarbyl siloxanes                                                                               |              |      21 |
| Aliphatic tertiary amines and oxides                                                                |              |      20 |
| Simple Lithium compounds                                                                            |              |      19 |
| mono-, dialkyl phosphate esters and salts                                                           |              |      19 |
| EDTA-related acids and salts                                                                        |              |      18 |
| Benzoates                                                                                           | chebi:16150  |      18 |
| Simple manganese compounds                                                                          |              |      17 |
| Aromatic primary monoamines                                                                         |              |      17 |
| Photoinitiators (benzoyl radical precursor type)                                                    |              |      17 |
| Brominated cycloalkanes, alcohols, phosphates, triazine triones, diphenyl ethers and diphenyl [...] |              |      17 |
| Esters from linear saturated dicarboxylic acids and branched aliphatic alcohols                     |              |      16 |
| Aliphatic nitriles                                                                                  | chebi:80291  |      16 |
| Organic hydroperoxides and aliphatic/cumyl peroxides                                                |              |      15 |
| Linear aliphatic ketones                                                                            |              |      15 |
| Organic phosphonic acids, salts and esters                                                          |              |      15 |
| Unsubstituted and linear aliphatic-substituted cyclic ketones                                       |              |      14 |
| Aliphatic primary amides                                                                            | chebi:65285  |      14 |
| Branched aliphatic-substituted cyclic ketones and polycyclic ketones                                |              |      14 |
| dithiocarbamate complexes                                                                           |              |      14 |
| Aliphatic secondary and tertiary amides                                                             |              |      13 |
| acrylate and methacrylate amines                                                                    |              |      13 |
| Benzene and its derivatives with linear aliphatic substituents                                      |              |      12 |
| Vinylbenzene derivatives                                                                            |              |      11 |
| Zirconium and its simple inorganic compounds                                                        |              |      11 |
| Ethoxylated and alcohols (other than methanol and ethanol); ethoxylated aromatic alcohols           |              |      11 |
| Ethoxylated alcohol sulfates                                                                        |              |      11 |
| Salicylate esters                                                                                   |              |      11 |
| substances containing 4-TBP                                                                         |              |      11 |
| Mono-, di-phenyl phosphite derivatives                                                              |              |      11 |
| Miscellaneous bisphenols                                                                            |              |      11 |
| Polyphenyls and its partially hydrogenated derivatives                                              |              |      11 |
| aromatic ethers                                                                                     | chebi:35618  |      10 |
| aliphatic sulfonic acids, hydroxyalkanesulfonic acids and their salts                               |              |      10 |
| succinic anhydrides                                                                                 | chebi:36595  |      10 |
| Arylamino anthraquinones                                                                            |              |      10 |
| Paraben acid, salts and esters                                                                      |              |      10 |
| Molybdenum and its simple compounds                                                                 |              |      10 |
| Rose ketones                                                                                        |              |      10 |
| triphenylphosphite and its derivatives                                                              |              |       9 |
| Ethoxylated alcohol phosphates and phosphinic acid derivatives                                      |              |       9 |
| 1,2-ethanediols and their carbonates                                                                |              |       9 |
| imidazoles                                                                                          | chebi:14434  |       9 |
| Triphenylphosphate derivatives                                                                      |              |       9 |
| Aralkylaldehydes                                                                                    |              |       8 |
| Chlorinated trialkylphosphates                                                                      |              |       8 |
| Acyl glycinates and sarcosinates                                                                    |              |       8 |
| Alkyl aryl and cyclic diaryl esters of phosphoric acid                                              |              |       8 |
| Ditriazine stilbenedisulfonic acid dyes (optical brighteners)                                       |              |       8 |
| Tetrabromobisphenol A derivatives                                                                   |              |       8 |
| (tetrahydro)furan primary alcohol derivatives and their oxidation products                          |              |       8 |
| aralkylamines                                                                                       | chebi:18000  |       7 |
| Linear diols                                                                                        |              |       7 |
| Bisphenol F (BPF) derivative                                                                        |              |       7 |
| Esters from branched or non-aromatic cyclic dicarboxylic acids and aliphatic alcohols               |              |       7 |
| Polycarboxylic acid monoamines, hydroxy derivatives and their salts with monovalent cations         |              |       7 |
| Aromatic nitriles                                                                                   |              |       6 |
| Cyclic ethers                                                                                       | chebi:37407  |       6 |
| Thioureas                                                                                           | chebi:36946  |       6 |
| Piperazine-functionalised polyamines                                                                |              |       6 |
| peroxide anhydrides (non-cyclic)                                                                    |              |       6 |
| Diazo amino hydroxyl naphthalenedisulfonic acid dyes                                                |              |       6 |
| Carboxylated/methylated nitrobenzenes and their derivatives                                         |              |       6 |
| N-alkoxy-2,2,6,6-tetramethylpiperidine derivatives                                                  |              |       6 |
| Trialkyl phosphates                                                                                 | chebi:37562  |       6 |
| Brominated phthalates                                                                               |              |       6 |
| (hydroxy)carboxylic acid amine chelates                                                             |              |       6 |
| Non-aromatic guanidines                                                                             |              |       5 |
| tetrahydroxymethyl and tetraalkyl phosphonium salts                                                 |              |       5 |
| simple vanadium compounds                                                                           |              |       5 |
| dibenzoyl peroxide derivatives                                                                      |              |       5 |
| Dibenzo oxaphosphorine oxide derivatives                                                            |              |       5 |
| Alkyldimethylbetaines                                                                               |              |       5 |
| thioxanthenones                                                                                     |              |       4 |
| nitroalkanes                                                                                        | chebi:7587   |       4 |
| Cyclic acetals from aldehydes                                                                       |              |       4 |
| Polyol amines                                                                                       |              |       4 |
| Inorganic Bromide Salts                                                                             |              |       4 |
| Guanidylureas, cyanoguanidines and biguanides                                                       |              |       4 |
| beta-hydroxyacids and their esters with aliphatic alcohols                                          |              |       3 |
| Yttrium and its simple compounds                                                                    |              |       3 |
| Branched/cyclic dialiphatic ethers (excluding alpha,beta-unsaturated ethers)                        |              |       3 |
| Hydroxy and alkoxy phenylketones                                                                    |              |       3 |
| Bisphenol AF (BPAF) derivatives                                                                     |              |       3 |
| Other aliphatic- or aryl-bridged bisphenol derivatives                                              |              |       3 |
| Alpha-chloro aliphatic carboxylate derivatives                                                      |              |       3 |
| Salicylic acid, its salts and alkylated derivatives                                                 |              |       3 |
| Methylene diphenyl ureas                                                                            |              |       2 |
| Fused tricyclic ethers with short chain polyalkyl substituents                                      |              |       2 |
| ethoxylated N-alkyltrimethylenediamines                                                             |              |       2 |
| Neodymium and its compounds                                                                         |              |       2 |
| Linear and branched alpha-beta unsaturated ketones                                                  |              |       2 |
| organic inorganic tin compounds without hydrocarbyl substituent                                     |              |       2 |
| Cardanols                                                                                           | chebi:186661 |       2 |
| Aminoureas, aminoguanidines and nitroguanidines                                                     |              |       2 |
| Sulfocarboxylic acids and esters (other than succinates)                                            |              |       2 |
| Dialkyl sulfates                                                                                    |              |       2 |
| Bisphenol S (BPS) derivatives                                                                       |              |       2 |
| Montan, carnauba and rice bran waxes and their derivatives                                          |              |       2 |
| Long chain aliphatic amino-acetic, -propionic and -succinic acids and their salts                   |              |       1 |
| Dialkyl (and diaryl) dithiophosphates (DDP)                                                         |              |       1 |
| Alkyl nitrates                                                                                      |              |       1 |
| thiocarbamates                                                                                      | chebi:38127  |       1 |
| Dihydropurinedione derivatives                                                                      |              |       1 |
| Pyrazoles                                                                                           | chebi:14973  |       1 |
| Amphoacetate and amphopropionate derivatives of N-hydroxyethylimidazolines                          |              |       1 |
| Hydroxyacid amides                                                                                  |              |       1 |
"""

ECHA_MAP: dict[str, Reference] = {
    "Ortho-phthalates": Reference.from_curie("CHEBI:26092", name="phthalate"),
    "Paraben acid, salts and esters": Reference.from_curie("CHEBI:85122", name="paraben"),
}

CHEBI_ROLE_MAP: dict[str, Reference] = {
    "plasticizer": Reference.from_curie("CHEBI:79056", name="plasticiser"),
    "catalyst": Reference.from_curie("CHEBI:35223", name="catalyst"),
    "monomer": Reference.from_curie("CHEBI:74236", name="polymerization monomer"),
    "antioxidant": Reference.from_curie("CHEBI:22586", name="antioxidant"),
    "flame retardant": Reference.from_curie("CHEBI:79314", name="flame retardant"),
    "blowing agent": Reference.from_curie("CHEBI:747328", name="blowing agent"),
    "filler": Reference.from_curie("CHEBI:747333", name="filler"),
    "stabilizer": Reference.from_curie("CHEBI:747331", name="stabilizer"),
    "colorant": Reference.from_curie("CHEBI:37958", name="dye"),  # TODO add synonym to ChEBI
    "pigment": Reference.from_curie("CHEBI:37958", name="dye"),  # TODO add synonym to ChEBI
    "lubricant": Reference.from_curie("CHEBI:747329", name="lubricant"),
    "biocide": Reference.from_curie(
        "CHEBI:33281", name="antimicrobial agent"
    ),  # TODO add synonym to ChEBI
    "solvent": Reference.from_curie("CHEBI:46787", name="solvent"),
    "emulsifier": Reference.from_curie("CHEBI:63046", name="emulsifier"),
    "surfactant": Reference.from_curie("CHEBI:35195", name="surfactant"),
    "anti-fog additive": Reference.from_curie("CHEBI:747327", name="anti-fog additive"),
    # this is the super class for processing aid
    "other processing aids": Reference.from_curie("CHEBI:747334", name="processing aids"),
    "antistatic agent": Reference.from_curie("CHEBI:747335", name="antistatic agent"),
    "adhesive": Reference.from_curie("CHEBI:747337", name="adhesive"),
    "unspecified additive": Reference.from_curie("CHEBI:747326", name="additive"),  # parent class
    "heat stabilizer": Reference.from_curie("CHEBI:747338", name="heat stabilizer"),
    "light stabilizer": Reference.from_curie("CHEBI:747339", name="light stabilizer"),
    "viscosity modifier": Reference.from_curie("CHEBI:747340", name="viscosity modifier"),
    "impact modifier": Reference.from_curie("CHEBI:747341", name="impact modifier"),
    "initiator": Reference.from_curie("CHEBI:747342", name="initiator"),
    "crosslinking agent": Reference.from_curie("CHEBI:50684", name="crosslinking agent"),
    "odor agent": Reference.from_curie("CHEBI:747343", name="odor agent"),
    "impurity": Reference.from_curie("CHEBI:143130", name="impurity"),
    "ultraviolet-absorbing agent": Reference.from_curie(
        "CHEBI:73335", name="ultraviolet-absorbing agent"
    ),
    "polymerization aid": Reference.from_curie("CHEBI:747345", name="polymerization aid"),
    # Non-intentionally added substances (NIAS)
    "nias": Reference.from_curie("CHEBI:747346", name="non-intentionally added substances"),
    # the following map up to NIAS
    "intermediate": Reference.from_curie("CHEBI:747346", name="intermediate"),
    "degradation product": Reference.from_curie("CHEBI:747346", name="degradation product"),
    # TODO not sure how to model this. other starting
    #  substances are initiator and monomer
    # "unspecified raw material": None,
}


def _get_sep(row: dict[str, Any], key: str) -> list[str]:
    if pd.notna(row[key]):
        return row[key].split(";")
    return []


if __name__ == "__main__":
    PlastChemGetter.cli()
