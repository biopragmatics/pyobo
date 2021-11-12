# -*- coding: utf-8 -*-

"""Tests for the OBO data structures."""

import unittest

from pyobo import Obo
from pyobo.struct.struct import BioregistryError


class TestStruct(unittest.TestCase):
    """Tests for the OBO data structures."""

    def test_invalid_prefix(self):
        """Test raising an error when an invalid prefix is used."""
        with self.assertRaises(BioregistryError):
            Obo(ontology="nope", name="", iter_terms=lambda: [])
