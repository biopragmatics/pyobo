"""Demo JSKOS."""

from pyobo.struct.jskos import read_jskos
from tqdm import tqdm


def _demo() -> None:
    url = "https://oer-repo.uibk.ac.at/w3id.org/vocabs/oefos2012/schema.json"
    o = read_jskos(url, prefix="oefos")
    tqdm.write(str(o))


if __name__ == "__main__":
    _demo()
