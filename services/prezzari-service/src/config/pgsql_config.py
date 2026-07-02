"""Shared-DB access to the same database the monolith reads (ADR-0001).

Mirrors the monolith's session-context helper: a lazily-created pooled engine,
a session that sets ``search_path`` to the shared ``public`` schema, and a
context manager that rolls back on error and always closes. The engine is built
on first use (not at import) so the app and its tests load without a database.

I Prezziari owns two snapshot tables (later slices); in this tracer slice the DB
is touched only for best-effort catalog self-registration.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

__all__ = ["get_session_context", "text"]

ENGINE_CONFIG = {
    "pool_size": 10,
    "max_overflow": 0,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def _get_session_factory() -> sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine(get_settings().database_url, **ENGINE_CONFIG)
        _session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=_engine
        )
    return _session_factory


@contextmanager
def get_session_context(schema: str = "public") -> Iterator[Session]:
    """Yield a session scoped to ``schema``, rolling back on error and always
    closing. I Prezziari reads the monolith's regions/areas by id/name only in
    the shared ``public`` schema, plus its own snapshot tables."""
    session = _get_session_factory()()
    session.execute(text(f"SET search_path TO {schema}"))
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
