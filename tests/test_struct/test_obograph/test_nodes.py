"""Tests for nodes."""

import unittest

from obographs.standardized import StandardizedNode

from pyobo import Reference
from pyobo.struct.obograph.reader import from_node


class TestImportNode(unittest.TestCase):
    """Test importing nodes from OBO graphs."""

    def test_simple_class(self) -> None:
        """Test a simple instance."""
        reference = Reference.from_curie("chebi:1234")
        node = StandardizedNode(reference=reference, type="CLASS", label="test class")
        term = from_node(node)
        self.assertEqual(reference, term.reference)
        self.assertEqual("test class", term.name)
        self.assertEqual("Term", term.type)

    def test_simple_instance(self) -> None:
        """Test a simple instance."""
        reference = Reference.from_curie("OMO:0001234")
        node = StandardizedNode(reference=reference, type="INDIVIDUAL", label="test individual")
        term = from_node(node)
        self.assertEqual(reference, term.reference)
        self.assertEqual("test individual", term.name)
        self.assertEqual("Instance", term.type)
