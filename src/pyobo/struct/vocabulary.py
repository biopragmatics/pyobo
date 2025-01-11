"""Reusable vocabulary."""

from collections.abc import Sequence

import curies
from curies import vocabulary as _v

from .reference import Reference

__all__ = [
    "equivalent_class",
    "has_contributor",
    "mapping_has_confidence",
    "mapping_has_justification",
]

RO_PREFIX = "RO"
BFO_PREFIX = "BFO"
IAO_PREFIX = "IAO"
SIO_PREFIX = "SIO"


def _c(c: curies.NamedReference) -> Reference:
    return Reference(prefix=c.prefix, identifier=c.identifier, name=c.name)


broad_match = _c(_v.broad_match)
close_match = _c(_v.close_match)
exact_match = _c(_v.exact_match)
narrow_match = _c(_v.narrow_match)
related_match = _c(_v.related_match)

mapping_has_justification = Reference(
    prefix="sssom", identifier="mapping_justification", name="mapping justification"
)
mapping_has_confidence = Reference(prefix="sssom", identifier="confidence", name="has confidence")
has_contributor = Reference(prefix="dcterms", identifier="contributor", name="contributor")
has_dbxref = Reference(
    prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
)
in_subset = Reference(prefix="oboInOwl", identifier="inSubset", name="in subset")
has_obo_namespace = Reference(prefix="oboInOwl", identifier="hasOBONamespace")

equivalent_class = Reference(prefix="owl", identifier="equivalentClass", name="equivalent class")
equivalent_property = Reference(
    prefix="owl", identifier="equivalentProperty", name="equivalent property"
)
owl_same_as = Reference(prefix="owl", identifier="sameAs", name="same as")
term_replaced_by = Reference(prefix="IAO", identifier="0100001", name="term replaced by")
alternative_term = Reference(prefix="IAO", identifier="0000118", name="alternative term")
has_ontology_root_term = Reference(
    prefix="IAO", identifier="0000700", name="has ontology root term"
)
see_also = Reference(prefix="rdfs", identifier="seeAlso", name="see also")
comment = Reference(prefix="rdfs", identifier="comment", name="comment")
label = Reference(prefix="rdfs", identifier="label", name="has label")

from_species = Reference(prefix=RO_PREFIX, identifier="0002162", name="in taxon")
species_specific = Reference(prefix="debio", identifier="0000007", name="species specific")
has_left_to_right_reaction = Reference(
    prefix="debio", identifier="0000007", name="has left-to-right reaction"
)
has_right_to_left_reaction = Reference(
    prefix="debio", identifier="0000008", name="has right-to-left reaction"
)
has_citation = Reference(prefix="debio", identifier="0000029", name="has citation")
has_description = Reference(prefix="dcterms", identifier="description", name="description")
has_license = Reference(prefix="dcterms", identifier="license", name="license")
has_title = Reference(prefix="dcterms", identifier="title", name="title")

has_part = Reference(prefix=BFO_PREFIX, identifier="0000051", name="has part")
part_of = Reference(prefix=BFO_PREFIX, identifier="0000050", name="part of")
orthologous = Reference(
    prefix=RO_PREFIX, identifier="HOM0000017", name="in orthology relationship with"
)
is_a = Reference(prefix="rdfs", identifier="subClassOf", name="subclass of")

xsd_string = Reference(prefix="xsd", identifier="string", name="string")
xsd_float = Reference(prefix="xsd", identifier="float", name="float")
xsd_integer = Reference(prefix="xsd", identifier="integer", name="integer")
xsd_boolean = Reference(prefix="xsd", identifier="boolean", name="boolean")
xsd_year = Reference(prefix="xsd", identifier="gYear", name="year")
xsd_uri = Reference(prefix="xsd", identifier="anyURI", name="URI")


CHARLIE = _c(_v.charlie)

#: See https://mapping-commons.github.io/sssom/spec-model/
match_typedefs: Sequence[Reference] = (
    broad_match,
    close_match,
    exact_match,
    narrow_match,
    related_match,
    owl_same_as,  # for instances
    equivalent_class,  # for classes
    equivalent_property,  # for properties
    has_dbxref,
    see_also,
)

# Extension past the SSSOM spec
extended_match_typedefs: Sequence[Reference] = (
    *match_typedefs,
    alternative_term,
    term_replaced_by,
)

#: These are predicates that have their own dedicated fields
#: in OBO and FunOWL output
SKIP_PROPERTY_PREDICATES_OBJECTS = [
    term_replaced_by,  # maps to "replaced_by:" line
    see_also,  # maps to "consider:" line
    alternative_term,  # maps to "alt_id:" line
]

SKIP_PROPERTY_PREDICATES_LITERAL = [
    comment,  # maps to "comment:" line with strings
]
