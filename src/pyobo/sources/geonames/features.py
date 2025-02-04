"""Get terms from GeoNames Features."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from pyobo import Obo, Term
from pyobo.sources.geonames.utils import PREFIX_FEATURE, get_feature_terms

__all__ = ["GeonamesFeatureGetter"]

logger = logging.getLogger(__name__)


class GeonamesFeatureGetter(Obo):
    """An ontology representation of GeoNames features."""

    ontology = PREFIX_FEATURE
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield from get_feature_terms(force=force)


if __name__ == "__main__":
    GeonamesFeatureGetter.cli()
