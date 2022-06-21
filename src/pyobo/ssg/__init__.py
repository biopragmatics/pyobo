"""Static site generator."""

from pathlib import Path
from typing import Union

import bioregistry
from jinja2 import Environment, FileSystemLoader
from tqdm import tqdm

from pyobo import Obo

__all__ = [
    "make_page",
    "make_site",
]

HERE = Path(__file__).parent.resolve()
environment = Environment(
    autoescape=True, loader=FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True
)
environment.globals["bioregistry"] = bioregistry
term_template = environment.get_template("term.html")
typedef_template = environment.get_template("typedef.html")
index_template = environment.get_template("index.html")


def make_site(obo: Obo, directory: Union[str, Path], use_subdirectories: bool = True):
    """Make a website in the given directory."""
    directory = Path(directory)
    directory.mkdir(exist_ok=True, parents=True)

    resource = bioregistry.get_resource(obo.ontology)
    if resource is None:
        raise KeyError

    directory.joinpath("index.html").write_text(index_template.render(obo=obo, resource=resource))

    terms = list(obo)
    for term in tqdm(terms, desc=f"{obo.ontology} website", unit="term", unit_scale=True):
        if use_subdirectories:
            subdirectory = directory.joinpath(term.identifier)
            subdirectory.mkdir(exist_ok=True, parents=True)
            path = subdirectory.joinpath("index.html")
        else:
            path = directory.joinpath(term.identifier).with_suffix(".html")
        path.write_text(term_template.render(term=term, obo=obo, resource=resource))

    for typedef in obo.typedefs or []:
        if typedef.prefix != obo.ontology:
            continue
        if use_subdirectories:
            subdirectory = directory.joinpath(typedef.identifier)
            subdirectory.mkdir(exist_ok=True, parents=True)
            path = subdirectory.joinpath("index.html")
        else:
            path = directory.joinpath(typedef.identifier).with_suffix(".html")
        path.write_text(typedef_template.render(typedef=typedef, obo=obo, resource=resource))


def _main():
    from pyobo.sources import HGNCGetter, UniProtPtmGetter

    for cls in [UniProtPtmGetter, HGNCGetter]:
        obo = cls()
        make_site(obo, f"/Users/cthoyt/Desktop/pyobo-sites/{obo.ontology}/")


if __name__ == "__main__":
    _main()
