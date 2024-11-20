"""Utilities for reading OBO files."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping

import bioontologies.relations
import bioontologies.upgrade
import bioregistry
from curies import ReferenceTuple

from pyobo.struct import Referenced, SynonymSpecificities, SynonymSpecificity, default_reference
from pyobo.struct.struct import Reference, SynonymTypeDef, Term, default_synonym_typedefs
from pyobo.struct.typedef import alternative_term

logger = logging.getLogger(__name__)

TARGET_URI_WARNINGS: Counter[tuple[str, str]] = Counter()


def _parse_object_curie(
    curie: str, *, strict: bool = True, node: Reference, ontology_prefix: str
) -> Reference | None:
    if curie.startswith("http"):
        _pref, _id = bioregistry.parse_iri(curie)
        if not _pref or not _id:
            if not TARGET_URI_WARNINGS[ontology_prefix, curie]:
                logger.warning("[%s] unable to contract target URI %s", node.curie, curie)
            TARGET_URI_WARNINGS[ontology_prefix, curie] += 1
            return None
        return Reference(prefix=_pref, identifier=_id)

    if xx := bioontologies.upgrade.upgrade(curie):
        logger.debug(f"upgraded {curie} to {xx}")
        return Reference(prefix=xx.prefix, identifier=xx.identifier)

    if ":" not in curie:
        reference = default_reference(ontology_prefix, curie)
        logger.info(
            "[%s] massaging unqualified curie `%s` into %s", node.prefix, curie, reference.curie
        )
        return reference

    return Reference.from_curie(curie, strict=strict, node=node)


def _chomp_specificity(s: str) -> tuple[SynonymSpecificity | None, str]:
    s = s.strip()
    for _specificity in SynonymSpecificities:
        if s.startswith(_specificity):
            return _specificity, s[len(_specificity) :].strip()
    return None, s


SYNONYM_UNDEFINED_WARNING: Counter[tuple[str, str]] = Counter()


def _lookup_sd(
    reference: Reference,
    synonym_typedefs: Mapping[ReferenceTuple, SynonymTypeDef],
    node: Reference,
    ontology_prefix: str,
) -> SynonymTypeDef | None:
    if reference.pair in synonym_typedefs:
        return synonym_typedefs[reference.pair]

    if reference.pair in default_synonym_typedefs:
        return default_synonym_typedefs[reference.pair]

    if not SYNONYM_UNDEFINED_WARNING[ontology_prefix, reference.curie]:
        logger.warning("[%s] undefined synonym type %s", node.curie, reference.curie)
    SYNONYM_UNDEFINED_WARNING[ontology_prefix, reference.curie] += 1
    return None


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

    reference = _parse_object_curie(
        stype_curie, strict=strict, node=node, ontology_prefix=ontology_prefix
    )
    if reference is None:
        logger.warning(
            "[%s] unable to parse synonym type `%s` in line %s", node.curie, stype_curie, s
        )
        return None, rest

    dd = _lookup_sd(reference, synonym_typedefs, node=node, ontology_prefix=ontology_prefix)
    return dd, rest


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
        reference = _parse_object_curie(
            curie, strict=strict, node=node, ontology_prefix=ontology_prefix
        )
        if reference is None:
            if not SYNONYM_REFERENCE_WARNED[ontology_prefix, curie]:
                logger.warning("[%s] unable to parse synonym reference: %s", node.curie, curie)
            SYNONYM_REFERENCE_WARNED[ontology_prefix, curie] += 1
            continue
        references.append(reference)
    return references, rest


def _parse_trailing_ref_list(rest: str, *, strict: bool = True, node: Reference) -> list[Reference]:
    rest = rest.lstrip("[").rstrip("]")  # FIXME this doesn't account for trailing annotations
    rv = []
    for curie in rest.split(","):
        curie = curie.strip()
        if not curie:
            continue
        reference = Reference.from_curie(curie, strict=strict, node=node)
        if reference is None:
            logger.warning("[%s] could not parse provenance CURIE: %s", node.curie, curie)
            continue
        rv.append(reference)
    return rv


def _chomp_axioms(
    s: str, *, strict: bool = True, node: Reference
) -> list[tuple[Reference, Reference]]:
    return []


RELATION_REMAPPINGS: Mapping[str, ReferenceTuple] = bioontologies.upgrade.load()


def _handle_relation_curie(
    curie: str,
    *,
    strict: bool = True,
    name: str | None = None,
    ontology_prefix: str,
    node: Reference | None = None,
) -> Reference | None:
    if curie in RELATION_REMAPPINGS:
        prefix, identifier = RELATION_REMAPPINGS[curie]
        return Reference(prefix=prefix, identifier=identifier)

    if curie.startswith("http"):
        _pref, _id = bioregistry.parse_iri(curie)
        if not _pref or not _id:
            logger.warning(
                "[%s] unable to contract relation URI %s",
                node.curie if node else ontology_prefix,
                curie,
            )
            return None
        return Reference(prefix=_pref, identifier=_id)
    elif ":" in curie:
        return Reference.from_curie(curie, name=name, strict=strict, node=node)
    elif xx := bioontologies.upgrade.upgrade(curie):
        logger.debug(f"upgraded {curie} to {xx}")
        return Reference(prefix=xx.prefix, identifier=xx.identifier)
    elif yy := _ground_rel_helper(curie):
        logger.debug(f"grounded {curie} to {yy}")
        return yy
    elif " " in curie:
        logger.warning("[%s] invalid typedef CURIE %s", ontology_prefix, curie)
        return None
    else:
        reference = default_reference(ontology_prefix, curie)
        logger.info(
            "[%s] massaging unqualified curie `%s` into %s", ontology_prefix, curie, reference.curie
        )
        return reference


def _ground_rel_helper(curie) -> Reference | None:
    a, b = bioontologies.relations.ground_relation(curie)
    if a is None or b is None:
        return None
    return Reference(prefix=a, identifier=b)


UNPARSED_IRIS: set[str] = set()


def _append_property(
    term: Term,
    prop: str | Reference | Referenced,
    value: str | Reference | Referenced,
    *,
    strict: bool,
    ontology_prefix: str,
) -> Term:
    """Append a property."""
    if isinstance(prop, str):
        # TODO do some relation upgrading here too!
        if prop.startswith("http://purl.obolibrary.org/obo/"):
            prop = Reference(
                prefix="obo", identifier=prop.removeprefix("http://purl.obolibrary.org/obo/")
            )
        elif prop.startswith("http"):
            # TODO upstream this into an omni-parser for references?
            _pref, _id = bioregistry.parse_iri(prop)
            if _pref and _id:
                prop = Reference(prefix=_pref, identifier=_id)
            else:
                logger.warning(f"[{term.curie}] unable to handle property: {prop}")
                return term
        else:
            _tmp_prop = _handle_relation_curie(
                prop,
                strict=strict,
                node=term.reference,
                ontology_prefix=ontology_prefix,
            )
            if _tmp_prop is None:
                logger.warning(f"[{term.curie}] could not parse property: {prop}")
                return term
            prop = _tmp_prop

    if not isinstance(value, str):
        return term.annotate_object(prop, value)

    if prop.prefix in ALWAYS_LITERAL:
        return term.annotate_literal(prop, value)

    if value.startswith("http"):
        _pref, _id = bioregistry.parse_iri(value)
        if _pref and _id:
            return term.annotate_object(prop, Reference(prefix=_pref, identifier=_id))
        else:
            if value not in UNPARSED_IRIS and not _ends_with_extension(value):
                logger.warning(
                    f"[{term.curie} {prop.curie}] could not parse property target as IRI: {value}"
                )
                UNPARSED_IRIS.add(value)
            return term

    if len(value) > 8 and value[:4].isnumeric() and value[4] == "-" and value[5:7].isnumeric():
        if len(value) == 10:  # it's YYYY-MM-DD
            return term.annotate_literal(
                prop, value, datatype=Reference(prefix="xsd", identifier="date")
            )
        # assume it's a full datetime
        return term.annotate_literal(
            prop, value, datatype=Reference(prefix="xsd", identifier="dateTime")
        )

    # assume if there's a string, then it's not a CURIE
    if " " in value:
        return term.annotate_literal(prop, value)

    if ":" in value:
        xx = Reference.from_curie(value, strict=strict)
        if xx is None:
            logger.warning(
                f"[{term.curie} {prop.curie}] could not parse property target as CURIE: {value}"
            )
            return term
        return term.annotate_object(prop, xx)

    return term.annotate_literal(prop, value)


SKIP_SUFFIXES = {".aspx", ".png", ".jpg", ".html", ".htm", ".pdf", ".svg"}


def _ends_with_extension(s: str) -> bool:
    return any(s.endswith(suff) for suff in SKIP_SUFFIXES)


ALWAYS_LITERAL: set[ReferenceTuple] = {alternative_term.pair}
