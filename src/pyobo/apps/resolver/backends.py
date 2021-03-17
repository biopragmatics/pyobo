# -*- coding: utf-8 -*-

"""Backends."""

import logging
from collections import Counter
from functools import lru_cache
from typing import Any, List, Mapping, Optional, Union

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pyobo import normalize_curie
from pyobo.constants import get_sqlalchemy_uri
from pyobo.identifier_utils import get_providers
import time
__all__ = [
    'Backend',
    'RawSQLBackend',
    'MemoryBackend',
    'SQLAlchemyBackend',
]

logger = logging.getLogger(__name__)


class Backend:
    """A resolution service."""

    def has_prefix(self, prefix: str) -> bool:
        """Check if there is a resource available with the given prefix."""
        raise NotImplementedError

    def get_primary_id(self, prefix: str, identifier: str) -> str:
        """Get the canonical identifier in the given resource."""
        raise NotImplementedError

    def get_name(self, prefix: str, identifier: str) -> Optional[str]:
        """Get the canonical/preferred (english) name for the identifier in the given resource."""
        raise NotImplementedError

    def get_synonyms(self, prefix: str, identifier: str) -> List[str]:
        """Get a list of synonyms."""
        raise NotImplementedError

    def get_xrefs(self, prefix: str, identifier: str) -> List[Mapping[str, str]]:
        """Get a list of xrefs."""
        raise NotImplementedError

    def summarize(self) -> Mapping[str, Any]:
        """Summarize the contents of the database."""
        raise NotImplementedError

    def count_curies(self) -> Optional[int]:
        """Count the number of identifiers in the database."""

    def count_alts(self) -> Optional[int]:
        """Count the number of alternative identifiers in the database."""

    def count_prefixes(self) -> Optional[int]:
        """Count the number of prefixes in the database."""

    def resolve(self, curie: str, resolve_alternate: bool = False) -> Mapping[str, Any]:
        """Return the results and summary when resolving a CURIE string."""
        prefix, identifier = normalize_curie(curie)
        if prefix is None or identifier is None:
            return dict(
                query=curie,
                success=False,
                message='Could not identify prefix',
            )

        providers = get_providers(prefix, identifier)
        if not self.has_prefix(prefix):
            rv = dict(
                query=curie,
                prefix=prefix,
                identifier=identifier,
                providers=providers,
                success=False,
                message=f'Could not find id->name mapping for {prefix}',
            )
            return rv

        name = self.get_name(prefix, identifier)

        if name is None and resolve_alternate:
            primary_id = self.get_primary_id(prefix, identifier)
            if primary_id != identifier:
                providers = get_providers(prefix, primary_id)
                name = self.get_name(prefix, primary_id)

        if name is None:
            return dict(
                query=curie,
                prefix=prefix,
                identifier=identifier,
                success=False,
                providers=providers,
                message='Could not look up identifier',
            )

        return dict(
            query=curie,
            prefix=prefix,
            identifier=identifier,
            name=name,
            success=True,
            providers=providers,
        )


class MemoryBackend(Backend):
    """A resolution service using a dictionary-based in-memory cache."""

    def __init__(self, get_id_name_mapping, get_alts_to_id, summarize) -> None:  # noqa:D107
        self.get_id_name_mapping = get_id_name_mapping
        self.get_alts_to_id = get_alts_to_id
        self.summarize = summarize

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        return self.get_id_name_mapping(prefix) is not None

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        alts_to_id = self.get_alts_to_id(prefix)
        return alts_to_id.get(identifier, identifier)

    def get_name(self, prefix: str, identifier: str) -> Optional[str]:  # noqa:D102
        id_name_mapping = self.get_id_name_mapping(prefix) or {}
        return id_name_mapping.get(identifier)


class RawSQLBackend(Backend):
    """A backend that communicates with low-level SQL statements."""

    def __init__(
        self, *,
        refs_table: Optional[str] = None,
        alts_table: Optional[str] = None,
        engine: Union[None, str, Engine] = None,
    ):  # noqa:D107
        if engine is None:
            self.engine = create_engine(get_sqlalchemy_uri())
        elif isinstance(engine, str):
            self.engine = create_engine(engine)
        else:
            self.engine = engine

        self.refs_table = refs_table or 'obo_reference'
        self.alts_table = alts_table or 'obo_alt'

    @lru_cache(maxsize=1)
    def count_curies(self) -> int:  # noqa:D102
        """Get the number of terms."""
        logger.info('counting CURIEs')
        start = time.time()
        rv = self._get_one(f'SELECT COUNT(id) FROM {self.refs_table};')  # noqa:S608
        logger.info('done counting CURIEs after %.2fs', time.time() - start)
        return rv

    @lru_cache(maxsize=1)
    def count_prefixes(self) -> int:  # noqa:D102
        logger.info('counting prefixes')
        return self._get_one(f'SELECT COUNT(DISTINCT prefix) FROM {self.refs_table};')  # noqa:S608

    @lru_cache(maxsize=1)
    def count_alts(self) -> Optional[int]:  # noqa:D102
        logger.info('counting alts')
        return self._get_one(f'SELECT COUNT(id) FROM {self.alts_table};')  # noqa:S608

    def _get_one(self, sql: str):
        with self.engine.connect() as connection:
            result = connection.execute(sql).fetchone()
            return result[0]

    def summarize(self) -> Counter:  # noqa:D102
        sql = f'SELECT prefix, COUNT(identifier) FROM {self.refs_table} GROUP BY prefix;'  # noqa:S608
        with self.engine.connect() as connection:
            return Counter(dict(connection.execute(sql).fetchall()))

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        sql = text(f"SELECT prefix FROM {self.refs_table} WHERE prefix = :prefix LIMIT 1;")  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix).fetchone()
            return bool(result)

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        sql = text(f'''
            SELECT identifier
            FROM {self.alts_table}
            WHERE prefix = :prefix and alt = :alt LIMIT 1;
        ''')  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix, alt=identifier).fetchone()
            return result[0] if result else identifier

    def get_name(self, prefix, identifier) -> Optional[str]:  # noqa:D102
        sql = text(f"""
            SELECT name
            FROM {self.refs_table}
            WHERE prefix = :prefix and identifier = :identifier LIMIT 1;
        """)  # noqa:S608
        with self.engine.connect() as connection:
            result = connection.execute(sql, prefix=prefix, identifier=identifier).fetchone()
            if result:
                return result[0]


class SQLAlchemyBackend(Backend):
    """A resolution service using a SQL database."""

    def summarize(self) -> Mapping[str, Any]:  # noqa:D102
        from pyobo.database.sql.models import Reference
        return dict(Reference.query.groupby(Reference.prefix).count())

    def has_prefix(self, prefix: str) -> bool:  # noqa:D102
        from pyobo.database.sql.models import Reference
        return Reference.query.filter(Reference.prefix == prefix).first()

    def get_primary_id(self, prefix: str, identifier: str) -> str:  # noqa:D102
        from pyobo.database.sql.models import Alt
        new_id = Alt.query.filter(Alt.prefix == prefix, Alt.alt == identifier).one_or_none()
        if new_id is None:
            return identifier
        return new_id.identifier

    def get_name(self, prefix, identifier) -> Optional[str]:  # noqa:D102
        from pyobo.database.sql.models import Reference
        reference = Reference.query.filter(Reference.prefix == prefix, Reference.identifier == identifier).one_or_none()
        if reference:
            return reference.name

    def get_synonyms(self, prefix: str, identifier: str) -> List[str]:  # noqa:D102
        from pyobo.database.sql.models import Synonym
        synonyms = Synonym.query.filter(Synonym.prefix == prefix, Synonym.identifier == identifier).all()
        return [s.name for s in synonyms]

    def get_xrefs(self, prefix: str, identifier: str) -> List[Mapping[str, str]]:  # noqa:D102
        from pyobo.database.sql.models import Xref
        xrefs = Xref.query.filter(Xref.prefix == prefix, Xref.identifier == identifier).all()
        xrefs = {(xref.xref_prefix, xref.xref_identifier) for xref in xrefs}
        return [
            dict(prefix=xref_prefix, identifier=xref_identifier)
            for xref_prefix, xref_identifier in sorted(xrefs)
        ]
