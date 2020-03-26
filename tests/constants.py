# -*- coding: utf-8 -*-

"""Constants for tests for PyOBO."""

import os
import pathlib

HERE = os.path.abspath(os.path.dirname(__file__))
RESOURCES = os.path.join(HERE, 'resources')

TEST_CHEBI_OBO_PATH = os.path.join(RESOURCES, 'test_chebi.obo')
TEST_CHEBI_OBO_URL = pathlib.Path(TEST_CHEBI_OBO_PATH).as_uri()

TEST_GMT_PATH = os.path.join(RESOURCES, 'test_msigdb.gmt')
TEST_WP_GMT_PATH = os.path.join(RESOURCES, 'test_wikipathways.gmt')
