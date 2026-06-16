"""The Notification wire contract.

A self-describing transient alert: a presentation `severity` (the ONLY domain-ish
vocabulary the Notifier knows) plus `title`/`body` text, and an optional `scope`.
It deliberately carries no domain event type — the producer classifies its event
into a severity before it ever reaches here (CONTEXT.md).
"""

from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warning", "success"]


class Scope(BaseModel):
    """An optional addressing hint expressed against a selection-bus axis (e.g.
    `{axis: "workshop", value: <beneId>}`). Both fields are required: a half-
    specified scope cannot be matched client-side, so pydantic rejects it rather
    than letting it pass as global. The server still broadcasts to everyone — the
    match is a client-side filter (slice 5), never a server room.
    """

    axis: str
    value: str


class Notification(BaseModel):
    severity: Severity
    title: str
    body: str
    scope: Scope | None = None
