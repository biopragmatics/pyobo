"""Static site generator."""

from pathlib import Path
from typing import Union

from jinja2 import Environment, FileSystemLoader
from pyobo import Obo
import bioregistry
__all__ = [
    "make_page",
    "make_site",
]

HERE = Path(__file__).parent.resolve()
environment = Environment(autoescape=True, loader=FileSystemLoader(HERE), trim_blocks=False)
environment.globals["bioregistry"] = bioregistry
index_template = environment.get_template("term.html")


def make_site(obo: Obo, directory: Union[str, Path], use_subdirectories: bool = True):
    """Make a website in the given directory."""
    directory = Path(directory)
    directory.mkdir(exist_ok=True, parents=True)
    for term in obo:
        if use_subdirectories:
            subdirectory = directory.joinpath(term.identifier)
            subdirectory.mkdir(exist_ok=True, parents=True)
            path = subdirectory.joinpath("index.html")
        else:
            path = directory.joinpath(term.identifier).with_suffix(".html")
        path.write_text(index_template.render(term=term, obo=obo))


def _main():
    from pyobo.sources.uniprot import UniProtPtmGetter
    obo = UniProtPtmGetter()
    make_site(obo, "/Users/cthoyt/Desktop/ptm-test/")


if __name__ == '__main__':
    _main()
