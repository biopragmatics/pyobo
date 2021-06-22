# -*- coding: utf-8 -*-

"""Tests for identifiers.org URL generation."""

import logging
import unittest

import requests
from bioregistry import get_identifiers_org_url

logger = logging.getLogger(__name__)

#: These resources don't seem to exist anymore
BLACKLIST = {
    "abs",
    "aftol.taxonomy",
    "agricola",
    "ecogene",
    "euclinicaltrials",
    "fsnp",
    "gold",
    "gold.genome",
    "gold.meta",
}

#: These resources will need special rules for resolving
UNSOLVED = {
    "ark",
    "did",
    "gramene.growthstage",
    "gwascentral.phenotype",
    # TODO
}


class TestMiriam(unittest.TestCase):
    """Test generating identifiers.org links."""

    def test_successful(self):
        """Test CURIEs that should work."""
        curies = [
            ("go", "0006915"),  # name in LUI
            ("doid", "11337"),  # name in LUI
            ("mesh", "C000100"),  # namespace not in LUI
        ]

        # curies = []
        # for entry in get_miriam():
        #     prefix = entry['prefix']
        #     if prefix <= 'gramene.growthstage':  # TODO REMOVE THIS LINE
        #         continue  # TODO REMOVE THIS LINE
        #     norm_prefix = normalize_prefix(prefix)
        #     self.assertIsNotNone(norm_prefix, msg=f'could not normalize MIRIAM prefix: {norm_prefix}')
        #     curies.append((prefix, norm_prefix, entry['sampleId']))

        for prefix, identifier in curies:
            if prefix in BLACKLIST or prefix in UNSOLVED:
                continue
            with self.subTest(prefix=prefix, msg=f"failed for MIRIAM prefix: {prefix}"):
                url = get_identifiers_org_url(prefix, identifier)
                self.assertIsNotNone(url, msg=f"metaregistry does not contain prefix {prefix}")
                try:
                    res = requests.get(url)
                except (
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                ):
                    logger.warning(f"identifiers.org has a problem resolving prefix {prefix}")
                    continue
                self.assertFalse(
                    res.text.startswith("INVALID"),
                    msg=f"invalid url for {prefix}: {url}\n\n{res.text}",
                )

    def test_unsuccessful(self):
        """Test links that should fail."""
        curies = [
            ("nope_nope_nope", "0006915"),
        ]
        for prefix, identifier in curies:
            with self.subTest(prefix=prefix):
                url = get_identifiers_org_url(prefix, identifier)
                self.assertIsNone(url)
