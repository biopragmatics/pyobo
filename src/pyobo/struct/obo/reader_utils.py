"""Utilities for reading OBO files."""

from __future__ import annotations

import logging
import typing as t
from collections import Counter
from collections.abc import Mapping, Sequence

import click
from curies import ReferenceTuple
from curies import vocabulary as v

from pyobo.struct.reference import (
    OBOLiteral,
    _obo_parse_identifier,
    _parse_reference_or_uri_literal,
)
from pyobo.struct.struct import Reference, SynonymTypeDef, _synonym_typedef_warn
from pyobo.struct.struct_utils import Annotation

logger = logging.getLogger(__name__)

TARGET_URI_WARNINGS: Counter[tuple[str, str]] = Counter()


def _chomp_specificity(s: str) -> tuple[v.SynonymScope | None, str]:
    s = s.strip()
    for _specificity in t.get_args(v.SynonymScope):
        if s.startswith(_specificity):
            return _specificity, s[len(_specificity) :].strip()
    return None, s


def _chomp_typedef(
    s: str,
    *,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    strict: bool = False,
    node: Reference,
    ontology_prefix: str,
    upgrade: bool,
) -> tuple[SynonymTypeDef | None, str]:
    if not s:
        # This might happen if a synonym is just given as a string
        return None, ""

    if s.startswith("[") or s.startswith("{"):
        # there's no typedef reference here, just return
        return None, s

    try:
        synonym_typedef_id, rest = (x.strip() for x in s.split(" ", 1))
    except ValueError as e:
        if "not enough values to unpack" not in str(e):
            raise

        # let's just check if this might be a CURIE all by itself.
        # if there's a space, we are out of luck, otherwise, let's
        # try to parse it like a curie
        if " " in s:
            # if there
            return None, s

        synonym_typedef_id, rest = s, ""

    reference = _obo_parse_identifier(
        synonym_typedef_id,
        strict=strict,
        node=node,
        ontology_prefix=ontology_prefix,
        upgrade=upgrade,
    )
    if reference is None:
        logger.warning(
            "[%s] unable to parse synonym type `%s` in line %s",
            node.curie,
            synonym_typedef_id,
            click.style(s, fg="yellow"),
        )
        return None, rest

    synonym_typedef = _synonym_typedef_warn(
        ontology_prefix, predicate=reference, synonym_typedefs=synonym_typedefs
    )
    return synonym_typedef, rest


SYNONYM_REFERENCE_WARNED: Counter[tuple[str, str]] = Counter()


def _chomp_references(
    s: str, *, strict: bool = False, node: Reference, ontology_prefix: str, line: str
) -> tuple[Sequence[Reference | OBOLiteral], str]:
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
        logger.warning(
            "[%s] missing closing square bracket in references: %s",
            node.curie,
            click.style(line, fg="yellow"),
        )
        return [], s

    first, rest = s.lstrip("[").split("]", 1)
    references = _parse_provenance_list(
        first,
        node=node,
        ontology_prefix=ontology_prefix,
        counter=SYNONYM_REFERENCE_WARNED,
        scope_text="synonym provenance",
        line=line,
        strict=strict,
    )
    return references, rest


def _chomp_axioms(s: str, *, strict: bool = False, node: Reference) -> list[Annotation]:
    return []


def _parse_provenance_list(
    curies_or_uris: str,
    node: Reference,
    ontology_prefix: str,
    counter: Counter[tuple[str, str]],
    scope_text: str,
    line: str,
    strict: bool,
) -> list[Reference | OBOLiteral]:
    rv = []
    for curie_or_uri_raw in curies_or_uris.strip().split(","):
        curie_or_uri_raw = curie_or_uri_raw.strip()
        if not curie_or_uri_raw:
            continue
        curie_or_uri, _, _ = curie_or_uri_raw.strip().partition(" ")
        if reference_or_literal := _parse_reference_or_uri_literal(
            curie_or_uri,
            node=node,
            ontology_prefix=ontology_prefix,
            counter=counter,
            context=scope_text,
            line=line,
            strict=strict,
        ):
            rv.append(reference_or_literal)
    return rv
