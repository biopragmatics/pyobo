# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

from __future__ import annotations

import configparser
import logging
import os

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker

from ...constants import PYOBO_CONFIG, PYOBO_HOME

logger = logging.getLogger(__name__)

# try loading from config file
uri = None
if os.path.exists(PYOBO_CONFIG):
    cfp = configparser.ConfigParser()
    logger.debug('reading configuration from %s', PYOBO_CONFIG)
    with open(PYOBO_CONFIG) as file:
        cfp.read_file(file)
    uri = cfp.get('pyobo', 'SQLALCHEMY_URI')
if uri is None:
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


class Resource(Base):
    """A resource."""

    __tablename__ = 'resource'
    prefix = Column(String, nullable=False, unique=True, index=True, primary_key=True)

    name = Column(String, nullable=False, unique=True, index=True)
    pattern = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    def __repr__(self) -> str:  # noqa:D105
        return self.prefix


class Reference(Base):
    """Represent a CURIE and label."""

    __tablename__ = 'reference'
    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'), primary_key=True)
    identifier = Column(String, primary_key=True)

    name = Column(String, index=True, nullable=True)

    resource = relationship(Resource)

    def __repr__(self) -> str:  # noqa:D105
        if self.name:
            return f'{self.prefix}:{self.identifier} ! {self.name}'
        return f'{self.prefix}:{self.identifier}'

    __table_args__ = (
        Index('reference_prefix_identifier_idx', prefix, identifier),
    )


class Synonym(Base):
    """Represent an OBO term's synonym."""

    __tablename__ = 'synonym'
    id = Column(Integer, primary_key=True)

    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'))
    identifier = Column(String)
    name = Column(String, index=True)

    resource = relationship(Resource)

    # specificity = Column(Enum(pyobo.struct.SynonymSpecifity))

    def __repr__(self) -> str:  # noqa:D105
        return self.name

    __table_args__ = (
        Index('synonym_prefix_identifier_idx', prefix, identifier),
    )


class Alt(Base):
    """Represents an alternate identifier relationship."""

    __tablename__ = 'alt'
    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'), primary_key=True)
    alt = Column(String, primary_key=True)

    identifier = Column(String, index=True)

    __table_args__ = (
        Index('alt_prefix_alt_idx', prefix, alt),
        Index('alt_prefix_identifier_idx', prefix, identifier),
        UniqueConstraint(prefix, identifier, alt),
    )


class Xref(Base):
    """Represents an equivalence in between terms in two resources."""

    __tablename__ = 'xref'
    id = Column(Integer, primary_key=True)

    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'))
    identifier = Column(String)

    xref_prefix = Column(String)
    xref_identifier = Column(String)

    source = Column(Text, index=True)

    __table_args__ = (
        Index('xref_prefix_identifier_idx', prefix, identifier),
        Index('xref_xprefix_xidentifier_idx', xref_prefix, xref_identifier),
    )
