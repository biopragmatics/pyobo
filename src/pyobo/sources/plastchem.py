"""Import PlastChem."""

from collections import Counter
from collections.abc import Iterable

import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from pyobo import Obo, get_grounder
from pyobo.struct import Reference, Term, TypeDef, default_reference
from pyobo.struct.typedef import exact_match, has_canonical_smiles, has_inchi, has_isomeric_smiles
from pyobo.utils.path import ensure_path

__all__ = ["PlastChemGetter"]
PREFIX = "plastchem"
URL = "https://zenodo.org/records/10701706/files/plastchem_db_v1.0.xlsx?download=1"

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
    f"{listn}_list": default_reference(PREFIX, f"{listn}_list") for listn in HAZARD_LISTS
}

HAZARD_LIST_ROOT = default_reference(PREFIX, "list")

TYPEDEF = TypeDef(reference=default_reference(PREFIX, "onList"))


class PlastChemGetter(Obo):
    """An ontology representation of PlastChem."""

    ontology = PREFIX
    static_version = "1.0"
    typedef = [
        TYPEDEF,
        has_inchi,
        has_canonical_smiles,
        has_isomeric_smiles,
        exact_match,
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Do it."""
    yield Term(reference=HAZARD_LIST_ROOT)
    for hazard_list_reference in HAZARD_LIST_REFERENCES.values():
        term = Term(reference=hazard_list_reference)
        term.append_parent(HAZARD_LIST_ROOT)
        yield term

    echa_counter = Counter()
    echa_examples = {}
    function_counter = Counter()
    function_examples = {}
    chebi_grounder = get_grounder("chebi")

    path = ensure_path(PREFIX, url=URL)
    df = pd.read_excel(path, sheet_name="Full database", dtype=str, skiprows=1)
    for _, row in df.iterrows():
        if pd.isna(row["plastchem_ID"]):
            continue

        name: str | None
        if pd.notna(row["pubchem_name"]):
            name = row["pubchem_name"]
        elif pd.notna(row["iupac_name"]):
            name = row["iupac_name"]
        else:
            name = None
        term = Term.from_triple(PREFIX, row["plastchem_ID"], name)

        cas = row.pop("cas")
        cas_fixed = row.pop("cas_fixed")
        if pd.notna(cas_fixed) and pd.notna(cas):
            if cas != cas_fixed.lstrip("'"):
                pass
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
                if match := chebi_grounder.get_best_match(echa_grouping):
                    echa_examples[echa_grouping] = match.curie, match.name
                elif match := chebi_grounder.get_best_match(echa_grouping.rstrip("s")):
                    echa_examples[echa_grouping] = match.curie, match.name

        # NIAS means non-intentionally added substance
        for func in _get_sep(row, "Harmonized_functions"):
            func = func.replace("_", " ").lower()
            function_counter[func] += 1
            if func not in function_examples and name is not None:
                if match := chebi_grounder.get_best_match(name):
                    if match.curie != "chebi:15702":
                        function_examples[func] = match.curie, match.name
                elif match := chebi_grounder.get_best_match(name.rstrip("s")):
                    if match.curie != "chebi:15702":
                        function_examples[func] = match.curie, match.name

        # TODO ECHA_grouping
        # TODO ground to chebi:
        #  - Harmonized_functions
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
                    echa_name,
                    m.curie if (m := chebi_grounder.get_best_match(echa_name)) else None,
                    count,
                )
                for echa_name, count in echa_counter.most_common()
            ],
            headers=["ECHA", "chebi", "count"],
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


CHEBI_ROLE_MAP = {
    "plasticizer": Reference.from_curie("CHEBI:79056", name="plasticiser"),
    "catalyst": Reference.from_curie("CHEBI:35223", name="catalyst"),
    "monomer": Reference.from_curie("CHEBI:74236", name="polymerization monomer"),
    "antioxidant": Reference.from_curie("CHEBI:22586", name="antioxidant"),
    "flame retardant": Reference.from_curie("CHEBI:79314"),
    "blowing agent": Reference.from_curie("CHEBI:747328"),
    "filler": Reference.from_curie("CHEBI:747333"),
    "stabilizer": Reference.from_curie("CHEBI:747331"),
    "colorant": Reference.from_curie("CHEBI:37958"),  # TODO add synonym
    "lubricant": Reference.from_curie("CHEBI:747329"),
    "biocide": Reference.from_curie("CHEBI:33281"),  # TODO add synonym
    "solvent": Reference.from_curie("CHEBI:46787"),
    "emulsifier": Reference.from_curie("CHEBI:63046"),
    "surfactant": Reference.from_curie("CHEBI:35195"),
    "anti-fog additive": Reference.from_curie("CHEBI:747327"),
    "other processing aids": Reference.from_curie(
        "CHEBI:747334"
    ),  # this is the super class for processing aid
    "antistatic agent": Reference.from_curie("CHEBI:747335"),
    "adhesive": Reference.from_curie("CHEBI:747337"),
    "unspecified additive": Reference.from_curie("CHEBI:747326"), # parent class
    "heat stabilizer": Reference.from_curie("CHEBI:747338"),
    "light stabilizer": Reference.from_curie("CHEBI:747339"),
    "viscocity modifier": Reference.from_curie("CHEBI:747340"),
    "impact modifier": Reference.from_curie("CHEBI:747341"),
}


def _get_sep(row, key):
    if pd.notna(row[key]):
        return row[key].split(";")
    return []


if __name__ == "__main__":
    PlastChemGetter.cli()
