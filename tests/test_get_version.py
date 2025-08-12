"""Tests for PyOBO version pins."""

import os
import unittest
from unittest import mock

from pyobo.api.utils import get_version, get_version_pins
from pyobo.utils.misc import _get_version_from_artifact, _prioritize_version, cleanup_version

MOCK_PYOBO_VERSION_PINS = '{"ncbitaxon": "2024-07-03", "vo":"2024-04-09", "chebi":"235", "bfo":5}'
FAULTY_MOCK_PYOBO_VERSION_PINS = "{'ncbitaxon': '2024-07-03'}"


@mock.patch.dict(os.environ, {"PYOBO_VERSION_PINS": MOCK_PYOBO_VERSION_PINS})
class TestVersionPins(unittest.TestCase):
    """Test using user-defined version pins."""

    def setUp(self):
        """Clear the cache before each test case."""
        get_version_pins.cache_clear()

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

    @mock.patch.dict(os.environ, {"PYOBO_VERSION_PINS": ""})
    def test_empty_version_pins(self):
        """Test empty version pins are processed correctly."""
        version_pins = get_version_pins()
        self.assertFalse(version_pins)

    @mock.patch.dict(os.environ, {"PYOBO_VERSION_PINS": FAULTY_MOCK_PYOBO_VERSION_PINS})
    def test_incorrectly_set_version_pins(self):
        """Test erroneously set version pins are processed correctly."""
        version_pins = get_version_pins()
        self.assertFalse(version_pins)


class TestVersionGetter(unittest.TestCase):
    """Test functions for getting versions."""

    def test_prov(self) -> None:
        """Test getting the version of prov."""
        v = _get_version_from_artifact("prov")
        self.assertEqual("20130430", v)

    def test_bao(self) -> None:
        """Test getting the version of BAO."""
        v = _prioritize_version(
            _get_version_from_artifact("bao"), ontology_prefix="bao", version=None, date=None
        )
        self.assertIsNone(v)

    def test_nmrcv(self) -> None:
        """Test the nmrCV version."""
        v = cleanup_version("http://nmrml.org/cv/v1.1.0/nmrCV", prefix="nmrcv")
        self.assertEqual("1.1.0", v)
