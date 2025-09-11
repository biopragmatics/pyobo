import requests
from typing import Iterable, Any
from pyobo.struct import Term, Reference
from tqdm import tqdm

PREFIX = "goldbook"
URL = "https://goldbook.iupac.org/terms/index/all/json/download"
XX = "https://goldbook.iupac.org/terms/view/{}/json"


def iter_terms() -> Iterable[Term]:
    res = requests.get(URL, timeout=15).json()
    for luid, record in tqdm(res['terms']['list'].items()):
        yield _get_term(luid, record)

def _get_term(luid: str, record: dict[str, Any]) -> Term:
    res = requests.get(XX.format(luid)).json()
    term = res['term']
    definitions = term['definitions']
    if definitions:
        definition = definitions[0]['text']
    else:
        definition = None

    return Term(
        reference=Reference(
            prefix=PREFIX,
            identifier=luid,
            name=record['title'],
        ),
        definition=definition,
    )
