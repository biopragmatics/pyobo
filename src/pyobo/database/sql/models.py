# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

from __future__ import annotations

import logging
import os
from sqlalchemy import Column, ForeignKey, Index, String, Text, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker

from ...constants import PYOBO_HOME

logger = logging.getLogger(__name__)

default_db_path = os.path.abspath(os.path.join(PYOBO_HOME, 'pyobo.db'))
# uri = os.environ.get('PYOBO_SQLALCHEMY_URI', f'sqlite:///{default_db_path}')
uri = 'postgresql+psycopg2://cthoyt:@localhost/obo'

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


class Synonym(Base):
    """Represent an OBO term's synonym."""

    __tablename__ = 'synonym'
    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'), primary_key=True)
    identifier = Column(String, primary_key=True)

    name = Column(String, index=True)

    resource = relationship(Resource)

    # specificity = Column(Enum(pyobo.struct.SynonymSpecifity))

    def __repr__(self) -> str:  # noqa:D105
        return self.name


class Alt(Base):
    """Represents an alternate identifier relationship."""

    __tablename__ = 'alt'
    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'), primary_key=True)
    alt = Column(String, primary_key=True)

    identifier = Column(String, index=True)



    __table_args__ = (
        # ForeignKeyConstraint(
        #     ('prefix', 'identifier'),
        #     (f'{Resource.__tablename__}.prefix', f'{Resource.__tablename__}.identifier'),
        # ),
        UniqueConstraint(prefix, identifier, alt),
        # Index('alt_xref_curie', prefix, alt),
    )


class Xref(Base):
    """Represents an equivalence in between terms in two resources."""

    __tablename__ = 'xref'
    prefix = Column(String, ForeignKey(f'{Resource.__tablename__}.prefix'), primary_key=True)
    identifier = Column(String, primary_key=True)

    xref_prefix = Column(String)
    xref_identifier = Column(String)

    source = Column(Text)

    __table_args__ = (
        # ForeignKeyConstraint(
        #     ('prefix', 'identifier'),
        #     (f'{Resource.__tablename__}.prefix', f'{Resource.__tablename__}.identifier'),
        # ),
        UniqueConstraint(prefix, identifier, xref_prefix, xref_identifier),
        Index('alt_xref_curie', xref_prefix, xref_identifier),
    )
