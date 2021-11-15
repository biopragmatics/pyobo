# -*- coding: utf-8 -*-

"""Tests for the OBO data structures."""

import unittest

from pyobo import Obo
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
