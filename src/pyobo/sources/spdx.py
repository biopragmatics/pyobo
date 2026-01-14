"""Convert SPDX to an ontology."""

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term, TypeDef
from pyobo.struct.typedef import see_also
from pyobo.struct.vocabulary import xsd_boolean
from pyobo.utils.path import ensure_json

__all__ = [
    "SPDXLicenseGetter",
]

DATA_URL = "https://github.com/spdx/license-list-data/raw/refs/heads/main/json/licenses.json"
LICENSE_PREFIX = "spdx"
TERM_PREFIX = "spdx.term"

ROOT = Term.from_triple(TERM_PREFIX, "ListedLicense", "listed license")
IS_OSI = TypeDef(
    reference=Reference(prefix=TERM_PREFIX, identifier="isOsiApproved", name="is OSI approved"),
    is_metadata_tag=True,
    domain=ROOT.reference,
    range=xsd_boolean,
)
IS_FSF = TypeDef(
    reference=Reference(prefix=TERM_PREFIX, identifier="isFsfLibre", name="is FSF Libre"),
    is_metadata_tag=True,
    domain=ROOT.reference,
    range=xsd_boolean,
)


def get_terms(version: str) -> Iterable[Term]:
    """Iterate over terms."""
    yield ROOT
    data = ensure_json(
        LICENSE_PREFIX,
        url=DATA_URL,
        version=version,
    )
    for record in data["licenses"]:
        if term := _get_term(record):
            yield term


def _get_term(record: dict[str, Any]) -> Term | None:
    try:
        reference = Reference(
            prefix=LICENSE_PREFIX, identifier=record["licenseId"], name=record["name"]
        )
    except ValidationError:
        tqdm.write(f"invalid: {record['licenseId']}")
        return None
    term = (
        Term(
            reference=reference,
            is_obsolete=True if record.get("isDeprecatedLicenseId") else None,
            # type="Instance",
        )
        .append_parent(ROOT)
        .append_synonym(record["licenseId"])
    )
    if record.get("isOsiApproved"):
        term.annotate_boolean(IS_OSI, True)
    if record.get("isFsfLibre"):
        term.annotate_boolean(IS_FSF, True)
    for uri in record.get("seeAlso", []):
        term.annotate_uri(see_also, uri)
    return term


class SPDXLicenseGetter(Obo):
    """An ontology representation of the SPDX Licenses."""

    bioversions_key = ontology = LICENSE_PREFIX
    typedefs = [see_also, IS_FSF, IS_OSI]
    root_terms = [ROOT.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise)


if __name__ == "__main__":
    SPDXLicenseGetter.cli()
