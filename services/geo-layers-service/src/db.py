"""Shared-DB access to the same postgres the monolith reads (ADR-0001).

A lazily-built pooled engine and a session scoped to the ``public`` schema. Built
on first use (not at import) so the app and a no-DB ``/health`` load fine.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.settings import get_settings

__all__ = ["get_session_context", "text"]

_session_factory: Optional[sessionmaker] = None


def _factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _session_factory


@contextmanager
def get_session_context(schema: str = "public") -> Iterator[Session]:
    session = _factory()()
    session.execute(text(f"SET search_path TO {schema}"))
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
