"""Convert ExPASy to OBO."""

import logging
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .utils import get_go_mapping
from ..struct import Annotation, Obo, OBOLiteral, Reference, Synonym, Term
from ..struct.typedef import enables, has_member, has_source, term_replaced_by
from ..utils.path import ensure_path

__all__ = [
    "ExpasyGetter",
]

PREFIX = "ec"
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
    typedefs = [has_member, enables, term_replaced_by, has_source]
    root_terms = [
        Reference(prefix=PREFIX, identifier="1"),
        Reference(prefix=PREFIX, identifier="2"),
        Reference(prefix=PREFIX, identifier="3"),
        Reference(prefix=PREFIX, identifier="4"),
        Reference(prefix=PREFIX, identifier="5"),
        Reference(prefix=PREFIX, identifier="6"),
        Reference(prefix=PREFIX, identifier="7"),
    ]
    property_values = [Annotation(has_source.reference, OBOLiteral.uri(EXPASY_DATABASE_URL))]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise, force=force)


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get the ExPASy terms."""
    tree_path = ensure_path(PREFIX, url=EXPASY_TREE_URL, version=version, force=force)
    with open(tree_path) as file:
        tree = get_tree(file)

    terms: dict[str, Term] = {}
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
        id_to_data = get_database(file)

    ec2go = get_ec2go(version=version)

    ec_code_to_alt_ids = {}
    for ec_code, data in id_to_data.items():
        if data.get("deleted"):
            terms[ec_code] = Term(
                reference=Reference(prefix=PREFIX, identifier=ec_code), is_obsolete=True
            )
            continue

        transfer_ids = data.get("transfer_id")
        if transfer_ids:
            term = terms[ec_code] = Term(
                reference=Reference(prefix=PREFIX, identifier=ec_code), is_obsolete=True
            )
            for transfer_id in transfer_ids:
                term.append_replaced_by(Reference(prefix=PREFIX, identifier=transfer_id))
            continue

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
            definition=data.get("reaction"),
        )
        for domain in data.get("domains", []):
            term.annotate_object(
                has_member,
                Reference.model_validate(
                    {"prefix": domain["namespace"], "identifier": domain["identifier"]},
                ),
            )
        for protein in data.get("proteins", []):
            term.annotate_object(
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


def normalize_expasy_id(expasy_id: str) -> str:
    """Return a standardized ExPASy identifier string.

    :param expasy_id: A possibly non-normalized ExPASy identifier
    :return: A normalized string.
    """
    return expasy_id.replace(" ", "")


def give_edge(unnormalized_ec_code: str) -> tuple[int, str | None, str]:
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


def get_database(lines: Iterable[str]) -> Mapping[str, dict[str, Any]]:
    """Parse the ExPASy database file and returns a list of enzyme entry dictionaries.

    :param lines: An iterator over the ExPASy database file or file-like
    :returns: A mapping from EC code to data
    """
    rv = {}
    for groups in _group_by_id(lines):
        _, expasy_id = groups[0]

        ec_data_entry: dict[str, Any] = {
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
                ec_data_entry["deleted"] = True
            elif descriptor == DE and value.startswith("Transferred entry: "):
                # TODO There's a situation where there are enough transfers that it goes on to a second line
                #  the following line just gives up on this one. or maybe I don't understand
                value = value.strip().removesuffix("and").rstrip(",").strip()
                ec_data_entry["transfer_id"] = _parse_transfer(value)
            elif descriptor == DE:
                if "name" not in ec_data_entry["concept"]:
                    ec_data_entry["concept"]["name"] = ""
                ec_data_entry["concept"]["name"] += value.rstrip(".")  # type:ignore
            elif descriptor == CA:
                if "reaction" not in ec_data_entry:
                    ec_data_entry["reaction"] = ""
                ec_data_entry["reaction"] += value.rstrip(".")  # type:ignore
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
                        {
                            "namespace": "uniprot",
                            "name": uniprot_accession,
                            "identifier": uniprot_id,
                        }
                    )

        rv[expasy_id] = ec_data_entry
    return rv


TRANSFER_SPLIT_RE = re.compile(r",\s*|\s+and\s+")


def _parse_transfer(value: str) -> list[str]:
    """Parse transferred entry string.

    :param value: A string for a transferred entry
    :returns: A list of EC codes that it got transferred to

    >>> _parse_transfer("Transferred entry: 1.1.1.198, 1.1.1.227 and 1.1.1.228.")
    ['1.1.1.198', '1.1.1.227', '1.1.1.228']
    """
    value = value[len("Transferred entry: ") :].rstrip().rstrip(".")
    return sorted(x.strip().removeprefix("and").strip() for x in TRANSFER_SPLIT_RE.split(value))


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


def get_ec2go(version: str) -> Mapping[str, set[tuple[str, str]]]:
    """Get the EC mapping to GO activities."""
    url = "http://current.geneontology.org/ontology/external2go/ec2go"
    path = ensure_path(PREFIX, url=url, name="ec2go.tsv", version=version)
    return get_go_mapping(path, "EC")


if __name__ == "__main__":
    ExpasyGetter.cli()
