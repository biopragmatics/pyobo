# -*- coding: utf-8 -*-

"""This module contains the base class for connection managers in SQLAlchemy."""

import logging
from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .models import Base

__all__ = [
    'Manager',
    'build_engine_session',
]

log = logging.getLogger(__name__)


def build_engine_session() -> Tuple:
    """Build a session."""
    engine = create_engine('sqlite:////Users/cthoyt/Desktop/obo.db')

    #: A SQLAlchemy session maker
    session_maker = sessionmaker(bind=engine)

    #: A SQLAlchemy session object
    session = scoped_session(session_maker)

    return engine, session


class Manager:
    """A wrapper around a SQLAlchemy engine and session."""

    #: The declarative base for this manager
    base = Base

    def __init__(self, engine=None, session=None) -> None:
        """Instantiate a manager from an engine and session."""
        if engine is None and session is None:
            engine, session = build_engine_session()
        self.engine = engine
        self.session = session

    def create_all(self, checkfirst: bool = True) -> None:
        """Create the PyBEL cache's database and tables.

        :param checkfirst: Check if the database exists before trying to re-make it
        """
        self.base.metadata.create_all(bind=self.engine, checkfirst=checkfirst)

    def drop_all(self, checkfirst: bool = True) -> None:
        """Drop all data, tables, and databases for the PyBEL cache.

        :param checkfirst: Check if the database exists before trying to drop it
        """
        self.session.close()
        self.base.metadata.drop_all(bind=self.engine, checkfirst=checkfirst)

    def bind(self) -> None:
        """Bind the metadata to the engine and session."""
        self.base.metadata.bind = self.engine
        self.base.query = self.session.query_property()

    def __repr__(self):  # noqa: D105
        return '<{} connection={}>'.format(self.__class__.__name__, self.engine.url)
