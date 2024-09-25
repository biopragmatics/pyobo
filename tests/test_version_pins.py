# -*- coding: utf-8 -*-

"""Tests for PyOBO VERSION_PINS."""

import unittest

from pyobo.api.utils import get_version
from pyobo.constants import VERSION_PINS


class TestVersionPins(unittest.TestCase):
    """Test using VERSION_PINS."""

    def test_correct_version_pin_types(self):
        """Test resource and version type."""
        for resource_prefix, version in VERSION_PINS.items():
            self.assertIsInstance(resource_prefix, str)
            self.assertIsInstance(version, str)

    def test_use_correct_version_pin(self):
        """Tests correct resource version is used."""
        for resource_prefix, version in VERSION_PINS.items():
            self.assertEqual(get_version(resource_prefix), version)
