# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

from __future__ import annotations

import logging
import os

from sqlalchemy import Column, ForeignKey, Integer, String, Table, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship, scoped_session, sessionmaker

from ...constants import PYOBO_HOME

logger = logging.getLogger(__name__)

default_db_path = os.path.abspath(os.path.join(PYOBO_HOME, 'pyobo.db'))
uri = os.environ.get('PYOBO_SQLALCHEMY_URI', f'sqlite:///{default_db_path}')

engine = create_engine(uri)

#: A SQLAlchemy session maker
session_maker = sessionmaker(bind=engine)

#: A SQLAlchemy session object
session = scoped_session(session_maker)

Base = declarative_base(bind=engine)


def create_all(checkfirst: bool = True) -> None:
    """Create all tables."""
    Base.metadata.create_all(checkfirst=checkfirst)


def drop_all() -> None:
    """Drop all tables."""
    Base.metadata.drop_all()


Base.query = session.query_property()

term_to_xref = Table(
    'xref',
    Base.metadata,
    Column('term_id', Integer, ForeignKey('term.id'), primary_key=True),
    Column('reference_id', Integer, ForeignKey('reference.id'), primary_key=True),
)


class Resource(Base):
    """A resource."""

    __tablename__ = 'resource'
    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)
    prefix = Column(String, nullable=False)
    pattern = Column(String, nullable=False)

    def __repr__(self) -> str:  # noqa:D105
        return self.prefix


class Reference(Base):
    """Represent a CURIE and label."""

    __tablename__ = 'reference'
    id = Column(Integer, primary_key=True)

    resource_id = Column(Integer, ForeignKey(f'{Resource.__tablename__}.id'), nullable=False, index=True)
    resource = relationship(Resource)
    identifier = Column(String, nullable=False)
    name = Column(String)

    @property
    def prefix(self) -> str:  # noqa:D401
        """The prefix for the reference, from the resource."""
        return self.resource.prefix

    def __repr__(self) -> str:  # noqa:D105
        if self.name:
            return f'{self.prefix}:{self.identifier} ! {self.name}'
        return f'{self.prefix}:{self.identifier}'


class Term(Base):
    """Represent an OBO term."""

    __tablename__ = 'term'
    id = Column(Integer, primary_key=True)

    reference_id = Column(Integer, ForeignKey(f'{Reference.__tablename__}.id'), nullable=False, index=True)
    reference = relationship(Reference)

    xrefs = relationship(
        Reference,
        secondary=term_to_xref,
        # lazy='dynamic',
        # backref=backref('terms', lazy='dynamic'),
    )


class Synonym(Base):
    """Represent an OBO term's synonym."""

    __tablename__ = 'synonym'
    id = Column(Integer, primary_key=True)

    term_id = Column(Integer, ForeignKey(f'{Term.__tablename__}.id'), nullable=False, index=True)
    term = relationship(Term, backref=backref('synonyms'))

    name = Column(String)

    # specificity = Column(Enum(pyobo.struct.SynonymSpecifity))

    def __repr__(self) -> str:  # noqa:D105
        return self.name
