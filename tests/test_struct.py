"""Tests for the OBO data structures."""

import unittest

from pyobo import Obo, Reference
from pyobo.struct.struct import BioregistryError


class Nope(Obo):
    """A class that will fail."""

    ontology = "nope"

    def iter_terms(self, force: bool = False):
        """Do not do anything."""


class TestStruct(unittest.TestCase):
    """Tests for the OBO data structures."""

    def test_invalid_prefix(self):
        """Test raising an error when an invalid prefix is used."""
        with self.assertRaises(BioregistryError):
            Nope()

    def test_reference_validation(self):
        """Test validation of prefix."""
        with self.assertRaises(ValueError):
            Reference(prefix="nope", identifier="also_nope")

        # For when we want to do regex checking
        # with self.assertRaises(ValueError):
        #     Reference(prefix="go", identifier="nope")
        # with self.assertRaises(ValueError):
        #     Reference(prefix="go", identifier="12345")

        r1 = Reference(prefix="go", identifier="1234567")
        self.assertEqual("go", r1.prefix)
        self.assertEqual("1234567", r1.identifier)

        r2 = Reference(prefix="GO", identifier="1234567")
        self.assertEqual("go", r2.prefix)
        self.assertEqual("1234567", r2.identifier)

        r3 = Reference(prefix="go", identifier="GO:1234567")
        self.assertEqual("go", r3.prefix)
        self.assertEqual("1234567", r3.identifier)

        r4 = Reference(prefix="GO", identifier="GO:1234567")
        self.assertEqual("go", r4.prefix)
        self.assertEqual("1234567", r4.identifier)
