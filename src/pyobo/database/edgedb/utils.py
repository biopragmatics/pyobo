# -*- coding: utf-8 -*-

"""Utilities for the EdgeDB loader."""

import os
from contextlib import closing, contextmanager

import edgedb
from easy_config import EasyConfig

from ...constants import PYOBO_HOME

PATH = os.path.join(PYOBO_HOME, 'config.ini')
HERE = os.path.abspath(os.path.dirname(__file__))
DDL_PATH = os.path.join(HERE, 'migration_0000.edgedb')


def get_ddl() -> str:
    """Get the DDL for the PyOBO EdgeDB."""
    with open(DDL_PATH) as file:
        return file.read().strip()


class PyoboConfig(EasyConfig):
    """Configuration for PyOBO."""

    FILES = [PATH]
    NAME = 'pyobo'

    #: Configuration for EdgeDB connection
    edgedb_uri: str = None

    def connect_edgedb(self):
        """Connect the database."""
        return edgedb.connect(self.edgedb_uri)


config = PyoboConfig.load()


@contextmanager
def test_connection():
    """Create a transaction for testing."""
    with closing(config.connect_edgedb()) as conn:
        try:
            transaction = conn.transaction()
            transaction.start()
            yield conn
        finally:
            transaction.rollback()
