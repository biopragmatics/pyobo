# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship

__all__ = [
    'Base',
    'Reference',
    'Term',
    'term_parents',
]

REFERENCE_TABLE_NAME = 'pyobo_reference'
TERM_TABLE_NAME = 'pyobo_term'
PARENTS_TABLE_NAME = 'pyobo_parents'

Base = declarative_base()

term_parents = Table(
    PARENTS_TABLE_NAME, Base.metadata,
    Column('term_id', Integer, ForeignKey(f'{TERM_TABLE_NAME}.id'), primary_key=True),
    Column('reference_id', Integer, ForeignKey(f'{REFERENCE_TABLE_NAME}.id'), primary_key=True),
)


class Reference(Base):
    """Represent a CURIE and label."""

    __tablename__ = REFERENCE_TABLE_NAME
    id = Column(Integer, primary_key=True)

    namespace = Column(String)
    identifier = Column(String)
    name = Column(String)


class Term(Base):
    """Represent an OBO term."""

    __tablename__ = TERM_TABLE_NAME
    id = Column(Integer, primary_key=True)

    reference_id = Column(Integer, ForeignKey(f'{Reference.__tablename__}.id'), nullable=False, index=True)
    reference = relationship(Reference)

    definition = Column(String)

    parents = relationship(
        Reference,
        secondary=term_parents,
        lazy='dynamic',
        backref=backref('children', lazy='dynamic'),
    )
