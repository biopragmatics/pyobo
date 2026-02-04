"""Test OBO lexical review."""

import unittest

from pyobo.cli.obo_review import do_it


class TestOboLexicalReview(unittest.TestCase):
    """Test OBO lexical review."""

    def test_it(self) -> None:
        """Test OBO lexical review."""
        matcher = ...
        graph_document = ...
        uri_prefix = ...
        passes, fails = do_it(
            matcher=matcher,
            graph_document=graph_document,
            uri_prefix=uri_prefix,
        )
        self.assertEqual([], passes)
        self.assertEqual([], fails)
