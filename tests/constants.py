"""Constants for tests for PyOBO."""

import pathlib
from unittest import mock

HERE = pathlib.Path(__file__).parent.resolve()
RESOURCES = HERE / "resources"

TEST_CHEBI_OBO_PATH = RESOURCES / "test_chebi.obo"
TEST_CHEBI_OBO_URL = pathlib.Path(TEST_CHEBI_OBO_PATH).as_uri()

TEST_GMT_PATH = RESOURCES / "test_msigdb.gmt"
TEST_WP_GMT_PATH = RESOURCES / "test_wikipathways.gmt"

chebi_patch = mock.patch(
    "pyobo.getters._ensure_ontology_path",
    side_effect=lambda *args, **kwargs: ("obo", TEST_CHEBI_OBO_PATH),
)
