# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

import logging

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker

from ...constants import get_sqlalchemy_uri

logger = logging.getLogger(__name__)

uri = get_sqlalchemy_uri()
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

    __tablename__ = "obo_resource"
    id = Column(Integer, primary_key=True)

    prefix = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    pattern = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    def __repr__(self) -> str:  # noqa:D105
        return self.prefix


class Reference(Base):
    """Represent a CURIE and label."""

    __tablename__ = "obo_reference"
    id = Column(Integer, primary_key=True)

    prefix = Column(String(32))
    identifier = Column(String(64))
    name = Column(String(4096))

    def __repr__(self) -> str:  # noqa:D105
        if self.name:
            return f"{self.prefix}:{self.identifier} ! {self.name}"
        return f"{self.prefix}:{self.identifier}"


class Alt(Base):
    """Represents an alternate identifier relationship."""

    __tablename__ = "obo_alt"
    id = Column(Integer, primary_key=True)

    prefix = Column(String(32))
    identifier = Column(String(64))
    alt = Column(String(64))

    def __repr__(self) -> str:  # noqa:D105
        return f"{self.prefix}:{self.alt}->{self.identifier}"


class Synonym(Base):
    """Represent an OBO term's synonym."""

    __tablename__ = "obo_synonym"
    id = Column(Integer, primary_key=True)

    prefix = Column(String(32), ForeignKey(f"{Resource.__tablename__}.prefix"))
    identifier = Column(String(64))
    name = Column(String, index=True)

    resource = relationship(Resource)

    # specificity = Column(Enum(pyobo.struct.SynonymSpecifity))

    def __repr__(self) -> str:  # noqa:D105
        return self.name

    __table_args__ = (Index("synonym_prefix_identifier_idx", prefix, identifier),)


class Xref(Base):
    """Represents an equivalence in between terms in two resources."""

    __tablename__ = "obo_xref"
    id = Column(Integer, primary_key=True)

    prefix = Column(String(32), ForeignKey(f"{Resource.__tablename__}.prefix"))
    identifier = Column(String(64))

    xref_prefix = Column(String(32))
    xref_identifier = Column(String(64))

    source = Column(Text, index=True)

    __table_args__ = (
        Index("xref_prefix_identifier_idx", prefix, identifier),
        Index("xref_xprefix_xidentifier_idx", xref_prefix, xref_identifier),
    )
