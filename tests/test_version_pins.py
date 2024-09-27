# -*- coding: utf-8 -*-

"""Tests for PyOBO VERSION_PINS."""
import os
import unittest
from unittest import mock

from pyobo.api.utils import get_version, get_version_pins

MOCK_VERSION_PINS = '{"ncbitaxon": "2024-07-03", "vo":"2024-04-09", ' '"chebi":"235", "bfo":5}'


@mock.patch.dict(os.environ, {"VERSION_PINS": MOCK_VERSION_PINS})
class TestVersionPins(unittest.TestCase):
    """Test using VERSION_PINS."""

    def test_correct_version_pin_types(self):
        """Test resource and version type."""
        version_pins = get_version_pins()
        for resource_prefix, version in version_pins.items():
            self.assertIsInstance(resource_prefix, str)
            self.assertIsInstance(version, str)

    def test_use_correct_version_pin(self):
        """Tests correct resource version is used."""
        version_pins = get_version_pins()
        for resource_prefix, version in version_pins.items():
            self.assertEqual(get_version(resource_prefix), version)
