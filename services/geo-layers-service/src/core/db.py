"""Shared-DB access to the same postgres the monolith reads (ADR-0001).

A lazily-built pooled engine and a session scoped to the ``public`` schema. Built
on first use (not at import) so the app and a no-DB ``/health`` load fine.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.core.settings import get_settings

__all__ = ["COMUNE_BOUNDARY_CTE", "get_session_context", "text"]

# Boundary of the clicked comune (Administrative Boundary, area_type_id = 3) for a
# bound :region_id — the SAME regions -> region_areas -> areas join the monolith's
# POI/areas layers use, in the shared public schema (ADR-0001). Every layer route
# prepends this CTE and filters/clips its features to `comune.geom`, so one map
# click scopes every layer to the same comune. ST_Union folds a multi-row boundary
# into a single geometry.
COMUNE_BOUNDARY_CTE = """
WITH comune AS (
    SELECT ST_Union(a.geom) AS geom
    FROM regions r
    JOIN region_areas ra ON ra.region_id = r.id
    JOIN areas a ON ra.area_id = a.id AND a.area_type_id = 3
    WHERE r.id = :region_id
)
"""

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
