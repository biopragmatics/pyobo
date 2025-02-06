"""Test references."""

import unittest

from pydantic import ValidationError

from pyobo import Reference


class TestReference(unittest.TestCase):
    """Test references."""

    def test_reference_with_spaces(self) -> None:
        """Test reference with spaces can't be validated as a CURIE."""
        with self.assertRaises(ValueError):
            Reference.from_curie("go:0123455677  asga")

    def test_validate_prefix(self) -> None:
        """Test reference with spaces can't be validated as a CURIE."""
        with self.assertRaises(ValidationError):
            Reference.from_curie("nope:nope")

    def test_superclass_validate(self) -> None:
        """Test that the from_curie function that's inherited returns the child class."""
        x = Reference.from_curie("go:1234567")
        self.assertIsInstance(x, Reference)
