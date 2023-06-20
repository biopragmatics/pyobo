# -*- coding: utf-8 -*-

"""Convert ExPASy to OBO."""

import logging
from collections import defaultdict
from typing import Dict, Iterable, Mapping, Optional, Set, Tuple

from .utils import get_go_mapping
from ..struct import Obo, Reference, Synonym, Term
from ..struct.typedef import enables, has_member
from ..utils.path import ensure_path

__all__ = [
    "ExpasyGetter",
]

PREFIX = "eccode"
EXPASY_DATABASE_URL = "ftp://ftp.expasy.org/databases/enzyme/enzyme.dat"
EXPASY_TREE_URL = "ftp://ftp.expasy.org/databases/enzyme/enzclass.txt"

logger = logging.getLogger(__name__)

#: The identifier of the entry (One)
ID = "ID"
#: Description (One)
DE = "DE"
#: Additional names/synonyms (Many)
AN = "AN"
#: Chemical Reaction String (One)
CA = "CA"
#: Comments (One - consider as free text)
CC = "CC"
#: List of cofactors? (Many)
CF = "CF"
#: ProSite Identifier (optional) (Many)
PR = "PR"
#: Reference to UniProt or SwissProt (Many)
DR = "DR"


class ExpasyGetter(Obo):
    """A getter for ExPASy Enzyme Classes."""

    bioversions_key = ontology = PREFIX
    typedefs = [has_member, enables]
    root_terms = [
        Reference(prefix="eccode", identifier="1"),
        Reference(prefix="eccode", identifier="2"),
        Reference(prefix="eccode", identifier="3"),
        Reference(prefix="eccode", identifier="4"),
        Reference(prefix="eccode", identifier="5"),
        Reference(prefix="eccode", identifier="6"),
        Reference(prefix="eccode", identifier="7"),
    ]
    idspaces = {
        "uniprot": "https://bioregistry.io/uniprot:",
        "eccode": "https://bioregistry.io/eccode:",
        "GO": "http://purl.obolibrary.org/obo/GO_",
        "RO": "http://purl.obolibrary.org/obo/RO_",
    }

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get ExPASy as OBO."""
    return ExpasyGetter(force=force)


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get the ExPASy terms."""
    tree_path = ensure_path(PREFIX, url=EXPASY_TREE_URL, version=version, force=force)
    with open(tree_path) as file:
        tree = get_tree(file)

    terms: Dict[str, Term] = {}
    child_to_parents = defaultdict(list)
    for ec_code, data in tree.items():
        terms[ec_code] = Term(
            reference=Reference(prefix=PREFIX, identifier=ec_code, name=data["name"]),
        )
        for child_data in data.get("children", []):
            child_ec_code = child_data["identifier"]
            child_to_parents[child_ec_code].append(ec_code)

    for child_ec_code, parents_ec_codes in child_to_parents.items():
        terms[child_ec_code].parents = [
            terms[parent_ec_code].reference for parent_ec_code in parents_ec_codes
        ]

    database_path = ensure_path(PREFIX, url=EXPASY_DATABASE_URL, version=version)
    with open(database_path) as file:
        _data = get_database(file)

    ec2go = get_ec2go(version=version)

    ec_code_to_alt_ids = {}
    for ec_code, data in _data.items():
        parent_ec_code = data["parent"]["identifier"]
        parent_term = terms[parent_ec_code]

        synonyms = [Synonym(name=synonym) for synonym in data.get("synonyms", [])]
        if data["alt_ids"]:
            alt_ids = data["alt_ids"][0].rstrip(".")
            if "and" not in alt_ids:
                ec_code_to_alt_ids[ec_code] = [
                    alt_ids,
                ]
            else:
                ec_code_to_alt_ids[ec_code] = [
                    alt_id.rstrip(",") for alt_id in alt_ids.split(" ") if alt_id != "and"
                ]

        concept = data["concept"]
        try:
            name = concept["name"]
        except KeyError:
            continue
            # raise

        term = terms[ec_code] = Term(
            reference=Reference(prefix=PREFIX, identifier=ec_code, name=name),
            parents=[parent_term.reference],
            synonyms=synonyms,
        )
        for domain in data.get("domains", []):
            term.append_relationship(
                has_member,
                Reference(prefix=domain["namespace"], identifier=domain["identifier"]),
            )
        for protein in data.get("proteins", []):
            term.append_relationship(
                has_member,
                Reference(
                    prefix=protein["namespace"],
                    identifier=protein["identifier"],
                    name=protein["name"],
                ),
            )
        for go_id, go_name in ec2go.get(ec_code, []):
            term.append_relationship(
                enables, Reference(prefix="GO", identifier=go_id, name=go_name)
            )

    return terms.values()


"""TREE"""


def normalize_expasy_id(expasy_id: str) -> str:
    """Return a standardized ExPASy identifier string.

    :param expasy_id: A possibly non-normalized ExPASy identifier
    """
    return expasy_id.replace(" ", "")


def give_edge(unnormalized_ec_code: str) -> Tuple[int, Optional[str], str]:
    """Return a (parent, child) tuple for given id."""
    levels = [x for x in unnormalized_ec_code.replace(" ", "").replace("-", "").split(".") if x]
    level = len(levels)

    if level == 1:
        parent_id = None
    else:
        parent_id = ".".join(levels[:-1])

    return level, parent_id, ".".join(levels)


def get_tree(lines: Iterable[str]):
    """Get the ExPASy tree mapping."""
    rv = {}
    for line in lines:
        if not line[0].isnumeric():
            continue
        level, parent_expasy_id, expasy_id = give_edge(line[:7])
        name = line[11:]
        name = name.strip().strip(".")

        rv[expasy_id] = {
            "concept": {
                "namespace": PREFIX,
                "identifier": expasy_id,
            },
            "name": name,
            "level": level,
            "children": [],
        }
        if parent_expasy_id is not None:
            rv[expasy_id]["parent"] = {
                "namespace": PREFIX,
                "identifier": parent_expasy_id,
            }
            rv[parent_expasy_id]["children"].append(rv[expasy_id]["concept"])  # type:ignore

    return rv


def get_database(lines: Iterable[str]) -> Mapping:
    """Parse the ExPASy database file and returns a list of enzyme entry dictionaries.

    :param lines: An iterator over the ExPASy database file or file-like
    """
    rv = {}
    for groups in _group_by_id(lines):
        _, expasy_id = groups[0]

        rv[expasy_id] = ec_data_entry = {
            "concept": {
                "namespace": PREFIX,
                "identifier": expasy_id,
            },
            "parent": {
                "namespace": PREFIX,
                "identifier": expasy_id.rsplit(".", 1)[0],
            },
            "synonyms": [],
            "cofactors": [],
            "domains": [],
            "proteins": [],
            "alt_ids": [],
        }

        for descriptor, value in groups[1:]:
            if descriptor == "//":
                continue
            elif descriptor == DE and value == "Deleted entry.":
                continue
            elif descriptor == DE and value.startswith("Transferred entry: "):
                value = value[len("Transferred entry: ") :].rstrip()
                ec_data_entry["transfer_id"] = value
            elif descriptor == DE:
                ec_data_entry["concept"]["name"] = value.rstrip(".")  # type:ignore
            elif descriptor == AN:
                ec_data_entry["synonyms"].append(value.rstrip("."))  # type:ignore
            elif descriptor == PR:
                value = value[len("PROSITE; ") : -1]  # remove trailing comma
                ec_data_entry["domains"].append(  # type:ignore
                    {
                        "namespace": "prosite",
                        "identifier": value,
                    }
                )
            elif descriptor == DR:
                for uniprot_entry in value.replace(" ", "").split(";"):
                    if not uniprot_entry:
                        continue
                    uniprot_id, uniprot_accession = uniprot_entry.split(",")
                    ec_data_entry["proteins"].append(  # type:ignore
                        dict(
                            namespace="uniprot",
                            name=uniprot_accession,
                            identifier=uniprot_id,
                        )
                    )

    for expasy_id, data in rv.items():
        transfer_id = data.pop("transfer_id", None)
        if transfer_id is not None:
            rv[expasy_id]["alt_ids"].append(transfer_id)  # type:ignore

    return rv


def _group_by_id(lines):
    """Group lines by identifier."""
    groups = []
    for line in lines:  # TODO replace with itertools.groupby
        line = line.strip()

        if line.startswith("ID"):
            groups.append([])

        if not groups:
            continue

        descriptor = line[:2]
        value = line[5:]

        groups[-1].append((descriptor, value))

    return groups


def get_ec2go(version: str) -> Mapping[str, Set[Tuple[str, str]]]:
    """Get the EC mapping to GO activities."""
    url = "http://current.geneontology.org/ontology/external2go/ec2go"
    path = ensure_path(PREFIX, url=url, name="ec2go.tsv", version=version)
    return get_go_mapping(path, "EC")


if __name__ == "__main__":
    ExpasyGetter.cli()
