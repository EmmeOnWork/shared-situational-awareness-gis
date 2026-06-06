from typing import Any, Optional

from pydantic import BaseModel


class DataResponse(BaseModel):
    """Canonical widget response contract, reused verbatim from the monolith
    (copied, not imported — ADR-0001) so the frontend can reuse rendering code.
    """

    label: str
    data: dict[str, Any]
    from_datetime: Optional[str] = None
    to_datetime: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
