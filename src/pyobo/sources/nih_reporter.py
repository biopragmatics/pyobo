"""A source for NIH RePORTER projects."""

from collections.abc import Iterable

import pandas as pd
from nih_reporter_downloader import get_projects_df

from pyobo import Reference
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED, Obo, Term, default_reference

__all__ = [
    "NIHReporterGetter",
]

PREFIX = "nihreporter.project"
PROJECTS_SUBSET = [
    "APPLICATION_ID",
    "PROJECT_TITLE",
]

PROJECT_TERM = (
    Term(reference=default_reference(PREFIX, "project", name="project"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)


class NIHReporterGetter(Obo):
    """An ontology representation of NIH RePORTER."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield CHARLIE_TERM
        yield HUMAN_TERM
        yield PROJECT_TERM
        yield from iterate_nih_reporter_projects()


def iterate_nih_reporter_projects() -> Iterable[Term]:
    """Iterate over NIH RePORTER projects."""
    projects_df = get_projects_df()
    for identifier, name in projects_df[PROJECTS_SUBSET].values:
        term = Term(
            reference=Reference(
                prefix=PREFIX,
                identifier=str(identifier),
                name=name.replace("\n", " ") if pd.notna(name) else None,
            ),
            type="Instance",
        )
        term.append_parent(PROJECT_TERM)
        # TODO there is a lot more information that can be added here
        yield term


if __name__ == "__main__":
    NIHReporterGetter.cli()
