# -*- coding: utf-8 -*-

"""Tests for identifiers.org URL generation."""

import unittest

import requests

from pyobo.identifier_utils import get_identifiers_org_link


class TestMiriam(unittest.TestCase):
    """Test generating identifiers.org links."""

    def test_successful(self):
        """Test CURIEs that should work."""
        curies = [
            ('go', '0006915'),  # name in LUI
            ('doid', '11337'),  # name in LUI
            ('mesh', 'C000100'),  # namespace not in LUI
        ]
        for prefix, identifier in curies:
            with self.subTest(prefix=prefix):
                url = get_identifiers_org_link(prefix, identifier)
                self.assertIsNotNone(url, msg=f'metaregistry does not contain prefix {prefix}')
                res = requests.get(url)
                self.assertFalse(res.text.startswith('INVALID'), msg=f'invalid url for {prefix}: {url}')

    def test_unsuccessful(self):
        """Test links that should fail."""
        curies = [
            ('nope_nope_nope', '0006915'),
        ]
        for prefix, identifier in curies:
            with self.subTest(prefix=prefix):
                url = get_identifiers_org_link(prefix, identifier)
                self.assertIsNone(url)
