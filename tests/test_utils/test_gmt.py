"""GMT tests."""

import unittest

from pyobo.sources.gmt_utils import parse_gmt_file, parse_wikipathways_gmt
from tests.constants import TEST_GMT_PATH, TEST_WP_GMT_PATH


class TestGMT(unittest.TestCase):
    """Test parsing GMT files."""

    def test_parse_standard(self):
        """Test parsing a standard GMT file."""
        x = list(parse_gmt_file(TEST_GMT_PATH))
        self.assertEqual(3, len(x))

        self.assertEqual("HALLMARK_TNFA_SIGNALING_VIA_NFKB", x[0][0])
        self.assertEqual(
            "http://www.gsea-msigdb.org/gsea/msigdb/cards/HALLMARK_TNFA_SIGNALING_VIA_NFKB", x[0][1]
        )
        self.assertEqual({"3726", "2920"}, x[0][2])

        self.assertEqual("HALLMARK_HYPOXIA", x[1][0])
        self.assertEqual("http://www.gsea-msigdb.org/gsea/msigdb/cards/HALLMARK_HYPOXIA", x[1][1])
        self.assertEqual({"5230", "5163", "2632"}, x[1][2])

        self.assertEqual("HALLMARK_CHOLESTEROL_HOMEOSTASIS", x[2][0])
        self.assertEqual(
            "http://www.gsea-msigdb.org/gsea/msigdb/cards/HALLMARK_CHOLESTEROL_HOMEOSTASIS", x[2][1]
        )
        self.assertEqual({"2224", "1595"}, x[2][2])

    def test_parse_wikipathways(self):
        """Test parsing a WikiPathways GMT file."""
        x = list(parse_wikipathways_gmt(TEST_WP_GMT_PATH))
        self.assertEqual(3, len(x))

        self.assertEqual("WP4400", x[0][0])
        self.assertEqual("20200310", x[0][1])
        self.assertEqual("", x[0][2])
        self.assertEqual("FABP4 in ovarian cancer", x[0][3])
        self.assertEqual("Homo sapiens", x[0][4])
        self.assertEqual({"574413", "2167"}, x[0][5])

        self.assertEqual("WP23", x[1][0])
        self.assertEqual("20200310", x[1][1])
        self.assertEqual("", x[1][2])
        self.assertEqual("B Cell Receptor Signaling Pathway", x[1][3])
        self.assertEqual("Homo sapiens", x[1][4])
        self.assertEqual({"4690", "5781", "11184", "6195"}, x[1][5])

        self.assertEqual("WP2333", x[2][0])
        self.assertEqual("20200310", x[2][1])
        self.assertEqual("", x[2][2])
        self.assertEqual("Trans-sulfuration pathway", x[2][3])
        self.assertEqual("Homo sapiens", x[2][4])
        self.assertEqual({"1786", "2730", "27430"}, x[2][5])
