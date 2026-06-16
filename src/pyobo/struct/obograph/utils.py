"""Testing utilities."""

import unittest
from typing import cast

import obographs as og
from curies import Reference
from obographs import StandardizedGraph, StandardizedMeta

from pyobo.constants import TypeDefType

__all__ = [
    "assert_graph_equal",
]


def assert_graph_equal(
    test_case: unittest.TestCase, expected: StandardizedGraph, actual: StandardizedGraph
) -> None:
    """Assert two graphs are equal."""
    if expected.meta is not None:
        test_case.assertIsNotNone(actual.meta)
        test_case.assertEqual(
            expected.meta.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True),
            cast(StandardizedMeta, actual.meta).model_dump(
                exclude_unset=True, exclude_none=True, exclude_defaults=True
            ),
        )

    # strip out extra info
    for node in actual.nodes:
        node.reference = Reference.from_reference(node.reference)

    test_case.assertEqual(
        {node.reference.curie: node for node in expected.nodes},
        {node.reference.curie: node for node in actual.nodes},
    )
    test_case.assertEqual(
        {node.as_str_triple(): node for node in expected.edges},
        {node.as_str_triple(): node for node in actual.edges},
    )
    excludes = {"nodes", "edges", "meta"}
    test_case.assertEqual(
        expected.model_dump(
            exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=excludes
        ),
        actual.model_dump(
            exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=excludes
        ),
    )


PROPERTY_TYPE_MAP: dict[TypeDefType, og.PropertyType] = {
    "annotation": "ANNOTATION",
    "data": "DATA",
    "object": "OBJECT",
}
INVERSE_PROPERTY_TYPE_MAP: dict[og.PropertyType, TypeDefType] = {
    v: k for k, v in PROPERTY_TYPE_MAP.items()
}
