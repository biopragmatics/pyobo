# -*- coding: utf-8 -*-

"""SQLAlchemy models for OBO."""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker

from pyobo import get_id_name_mapping, get_id_synonyms_mapping, registries

logger = logging.getLogger(__name__)

engine = create_engine('sqlite:////Users/cthoyt/Desktop/obo.db')

#: A SQLAlchemy session maker
session_maker = sessionmaker(bind=engine)

#: A SQLAlchemy session object
session = scoped_session(session_maker)

Base = declarative_base(bind=engine)


def _create_all():
    Base.metadata.create_all(checkfirst=True)


def _drop_all():
    Base.metadata.drop_all()


Base.query = session.query_property()


class Resource(Base):
    """A resource."""

    __tablename__ = 'resource'
    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)
    prefix = Column(String, nullable=False)
    pattern = Column(String, nullable=False)


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

    def __str__(self) -> str:  # noqa:D105
        if self.name:
            return f'{self.prefix}:{self.identifier} ! {self.name}'
        return f'{self.prefix}:{self.identifier}'


class Term(Base):
    """Represent an OBO term."""

    __tablename__ = 'term'
    id = Column(Integer, primary_key=True)

    reference_id = Column(Integer, ForeignKey(f'{Reference.__tablename__}.id'), nullable=False, index=True)
    reference = relationship(Reference)

    definition = Column(String)


class Synonym(Base):
    """Represent an OBO term's synonym."""

    __tablename__ = 'synonym'
    id = Column(Integer, primary_key=True)

    term_id = Column(Integer, ForeignKey(f'{Term.__tablename__}.id'), nullable=False, index=True)
    term = relationship(Term)

    name = Column(String)
    # specificity = Column(Enum(pyobo.struct.SynonymSpecifity))


SKIP = {
    'obi',
    'ncbigene',  # too big, refs axquired from  other dbs
    'pubchem.compound',  # to big, can't deal with this now
}


def load() -> None:
    """Load the database."""
    _drop_all()
    _create_all()

    mr = registries.get_metaregistry()

    prefix_to_resource: Dict[str, Resource] = {}
    for _, entry in sorted(mr.items()):
        if entry.prefix in SKIP:
            continue
        prefix_to_resource[entry.prefix] = resource = Resource(
            prefix=entry.prefix,
            name=entry.name,
            pattern=entry.pattern,
        )
        session.add(resource)

    failed_prefixes = set()
    curie_to_reference: Dict[Tuple[str, str], Reference] = {}
    curie_to_term: Dict[Tuple[str, str], Term] = {}
    for prefix in mr:
        if prefix in SKIP:
            continue

        try:
            id_to_name_mapping = get_id_name_mapping(prefix)
        except ValueError as e:
            failed_prefixes.add(prefix)
            logger.debug('failed for %s: %s', prefix, e)
            continue

        logger.info('loading names %s', prefix)
        for identifier, name in id_to_name_mapping.items():
            curie_to_reference[prefix, identifier] = reference = Reference(
                resource=prefix_to_resource[prefix],
                identifier=identifier,
                name=name,
            )
            session.add(reference)

            curie_to_term[prefix, identifier] = term = Term(
                reference=reference,
            )
            session.add(term)

    for prefix in mr:
        if prefix in SKIP or prefix in failed_prefixes:
            continue

        try:
            id_synonyms_mapping = get_id_synonyms_mapping(prefix)
        except ValueError as e:
            logger.debug('failed for %s: %s', prefix, e)
            continue

        logger.info('loading synonyms %s', prefix)
        for identifier, synonyms in id_synonyms_mapping.items():
            for synonym in synonyms:
                s = Synonym(
                    term=curie_to_term[prefix, identifier],
                    name=synonym,
                )
                session.add(s)

    logger.info('committing')
    session.commit()

    logger.info(f'number resources loaded: {Resource.query.count():,}')
    logger.info(f'number references loaded: {Reference.query.count():,}')
    logger.info(f'number terms loaded: {Term.query.count():,}')
    logger.info(f'number synonyms loaded: {Synonym.query.count():,}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    load()
