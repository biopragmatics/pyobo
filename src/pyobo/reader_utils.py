"""Utilities for reading OBO files."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping

from curies import ReferenceTuple

from pyobo.struct import SynonymSpecificities, SynonymSpecificity
from pyobo.struct.struct import Reference, SynonymTypeDef, _synonym_typedef_warn

logger = logging.getLogger(__name__)

TARGET_URI_WARNINGS: Counter[tuple[str, str]] = Counter()


def _chomp_specificity(s: str) -> tuple[SynonymSpecificity | None, str]:
    s = s.strip()
    for _specificity in SynonymSpecificities:
        if s.startswith(_specificity):
            return _specificity, s[len(_specificity) :].strip()
    return None, s


def _chomp_typedef(
    s: str,
    *,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    strict: bool = True,
    node: Reference,
    ontology_prefix: str,
) -> tuple[SynonymTypeDef | None, str]:
    if not s:
        # This might happen if a synonym is just given as a string
        return None, ""

    if s.startswith("[") or s.startswith("{"):
        # there's no typedef reference here, just return
        return None, s

    try:
        stype_curie, rest = (x.strip() for x in s.split(" ", 1))
    except ValueError as e:
        if "not enough values to unpack" not in str(e):
            raise

        # let's just check if this might be a CURIE all by itself.
        # if there's a space, we are out of luck, otherwise, let's
        # try to parse it like a curie
        if " " in s:
            # if there
            return None, s

        stype_curie, rest = s, ""

    reference = Reference.from_curie_or_uri(
        stype_curie,
        strict=strict,
        node=node,
        ontology_prefix=ontology_prefix,
    )
    if reference is None:
        logger.warning(
            "[%s] unable to parse synonym type `%s` in line %s", node.curie, stype_curie, s
        )
        return None, rest

    synonym_typedef = _synonym_typedef_warn(
        ontology_prefix, predicate=reference, synonym_typedefs=synonym_typedefs
    )
    return synonym_typedef, rest


SYNONYM_REFERENCE_WARNED: Counter[tuple[str, str]] = Counter()


def _chomp_references(
    s: str, *, strict: bool = True, node: Reference, ontology_prefix: str
) -> tuple[list[Reference], str]:
    if not s:
        return [], ""
    if not s.startswith("["):
        if s.startswith("{"):
            # This means there are no reference, but there are some qualifiers
            return [], s
        else:
            logger.debug("[%s] synonym had no references: %s", node.curie, s)
            return [], s

    if "]" not in s:
        logger.warning("[%s] missing closing square bracket in references: %s", node.curie, s)
        return [], s

    first, rest = s.lstrip("[").split("]", 1)
    references = []
    for curie in first.split(","):
        curie = curie.strip()
        if not curie:
            continue
        reference = Reference.from_curie_or_uri(
            curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if reference is None:
            if not SYNONYM_REFERENCE_WARNED[ontology_prefix, curie]:
                logger.warning("[%s] unable to parse synonym reference: %s", node.curie, curie)
            SYNONYM_REFERENCE_WARNED[ontology_prefix, curie] += 1
            continue
        references.append(reference)
    return references, rest


def _chomp_axioms(
    s: str, *, strict: bool = True, node: Reference
) -> list[tuple[Reference, Reference]]:
    return []
