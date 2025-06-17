"""Convert SPDX to an ontology."""

import json
from typing import Iterable

import requests
from pydantic import ValidationError
from tqdm import tqdm

from pyobo.struct import Obo, Term, Reference, TypeDef
from pyobo.struct.typedef import see_also
from pyobo.utils.path import ensure_path

__all__ = [
    "SPDXLicenseGetter",
]

DATA_URL = "https://github.com/spdx/license-list-data/raw/refs/heads/main/json/licenses.json"
LICENSE_PREFIX = 'spdx'
TERM_PREFIX = 'spdx.term'

IS_OSI = TypeDef(
    reference=Reference(prefix=TERM_PREFIX, identifier="isOsiApproved"),
    is_metadata_tag=True,
)
IS_FSF = TypeDef(
    reference=Reference(prefix=TERM_PREFIX, identifier="isFsfLibre"),
    is_metadata_tag=True,
)


def get_version():
    return requests.get(DATA_URL, timeout=5).json()['licenseListVersion']


def get_terms(version: str) -> Iterable[Term]:
    """Iterate over terms."""
    path = ensure_path(
        LICENSE_PREFIX,
        url=DATA_URL,
        version=version,
    )
    with path.open() as file:
        records = json.load(file)['licenses']
    for record in records:
        if term:=_get_term(record):
            yield term


def _get_term(record: dict[str, any]) -> Term | None:
    try:
        reference =Reference(prefix=LICENSE_PREFIX, identifier=record['licenseId'], name=record['name'])
    except ValidationError:
        tqdm.write(f"invalid: {record['licenseId']}")
        return None
    term = Term(
        reference=reference,
        is_obsolete=record['isDeprecatedLicenseId'],
    )
    if record.get('isOsiApproved'):
        term.annotate_boolean(IS_OSI, True)
    if record.get('isFsfLibre'):
        term.annotate_boolean(IS_FSF, True)
    for uri in record.get("seeAlso", []):
        term.annotate_uri(see_also, uri)
    return term


class SPDXLicenseGetter(Obo):
    """An ontology representation of the SPDX Licenses."""

    bioversions_key = ontology = LICENSE_PREFIX
    typedefs = [see_also, IS_FSF, IS_OSI]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(version=self._version_or_raise)


if __name__ == '__main__':
    SPDXLicenseGetter.cli()
