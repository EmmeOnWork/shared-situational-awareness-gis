"""Per-Bene anonymous Chat store (pure core).

A continuous, append-only deliberation log that spans *all* of a Bene's Rounds
(service CONTEXT "Chat"). ``append`` is **gated** on the current ``ProcessState``:
it preserves Vote independence by rejecting any message whose author has not yet
cast their Vote in the current Round. ``read`` returns the **fully anonymised**
shape — no author is ever surfaced — so the analysable record carries only the
Round number, timestamp and body. No IO, no DB, no WebSocket; the room/persistence
layers turn the emitted ``MessagePosted`` into live fan-out and rows.
"""

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class ChatMessage:
    """The internal record. ``author_id`` is retained for abuse control only and
    is **never** exposed past this module."""

    round_number: int
    author_id: str
    body: str
    timestamp: datetime


@dataclass(frozen=True)
class AnonymousMessage:
    """The read/analysable/broadcast shape — author identity is excluded."""

    round_number: int
    body: str
    timestamp: datetime


@dataclass(frozen=True)
class MessagePosted:
    """Side-effect: a new (anonymised) message to fan out over the Bene's WS room."""

    poi_id: str
    message: AnonymousMessage


@dataclass(frozen=True)
class ChatLog:
    poi_id: str
    messages: tuple[ChatMessage, ...] = ()


def empty_chat(poi_id: str) -> ChatLog:
    """An empty per-Bene Chat stream."""
    return ChatLog(poi_id=poi_id)


def _anonymise(message: ChatMessage) -> AnonymousMessage:
    """Project an internal record to its read/broadcast shape, dropping the author
    — the single place identity is stripped, so no surface can leak it."""
    return AnonymousMessage(
        round_number=message.round_number,
        body=message.body,
        timestamp=message.timestamp,
    )


def append(log: ChatLog, state, author_id: str, body: str, *, now: datetime):
    """Append ``body`` by ``author_id``, gated on the current Round ``state``.

    Rejected (ValueError) unless the author has cast their Vote in the current
    Round — the write-gate that keeps Votes independent.
    """
    if state.phase != "voting":
        raise ValueError(f"Chat is read-only in phase {state.phase!r}")
    if author_id not in state.votes:
        raise ValueError(f"cannot post before voting this Round: {author_id!r}")
    message = ChatMessage(
        round_number=state.round_number,
        author_id=author_id,
        body=body,
        timestamp=now,
    )
    return replace(log, messages=log.messages + (message,)), [
        MessagePosted(poi_id=log.poi_id, message=_anonymise(message))
    ]


def read(log: ChatLog) -> tuple[AnonymousMessage, ...]:
    """The Chat's full stream in the anonymised read shape (author excluded)."""
    return tuple(_anonymise(m) for m in log.messages)
